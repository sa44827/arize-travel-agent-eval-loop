# Build Log — Arize FDE Eval Loop

Running log of every real issue encountered building this project from scratch.
Useful for: the presentation deck, onboarding other engineers, and sharing with
the Arize team as genuine field notes on the Phoenix + google-genai stack.

---

## Issues Encountered

---

### #1 — Anthropic → Gemini port required
**What:** The sample repo was hardwired to `anthropic` SDK. No Anthropic key available.  
**Fix:** Rewrote `agent/loop.py` to `google-genai` function-calling API. Kept the `run_agent(messages) -> (reply, messages)` signature so `chat.py` and `api.py` were untouched.  
**Gotcha:** `google-genai` `GenerateContentConfig` takes `parameters_json_schema=` directly (accepts the Anthropic-format `input_schema` dict as-is). No tool schema translation needed.  
**Lesson:** The Anthropic tool schema format and Gemini's `parameters_json_schema` are close enough to reuse without transformation.

---

### #2 — Model availability on free-tier key
**What:** `.env.example` had `gemini-2.5-flash` and `gemini-2.5-pro` as defaults. Both returned 404 or were retired.  
**Fix:** Listed available models via `client.models.list()`, tested each with a live call, settled on `gemini-3.5-flash` (agent) and `gemini-3.1-pro-preview` (judge).  
**Lesson:** Always probe model availability at build time. Model names on free-tier change without notice.

---

### #3 — Phoenix `register()` crashes when called from stdin/inline scripts
**What:** Importing `phoenix.otel` from a `-c` inline Python command caused a `strawberry` GraphQL schema resolution error (`OSError: [WinError 123] The filename, directory name, or volume label syntax is incorrect: '<stdin>'`).  
**Fix:** Only call `register()` from a proper `.py` file, never from `-c` or `<<'E'` heredocs.  
**Lesson:** Phoenix's schema builds lazily on import. `<stdin>` as a filename breaks `pathlib.samefile()` deep in the strawberry type resolver.

---

### #4 — `dotenv.load_dotenv()` fails from stdin
**What:** `load_dotenv()` calls `find_dotenv()` which walks up from the current frame's `__file__`. From stdin, `frame.f_back` is `None` → `AssertionError`.  
**Fix:** Always call `load_dotenv(".env")` with an explicit path, or run from a proper file.  
**Lesson:** `find_dotenv()` is frame-based. Breaks in any non-file execution context.

---

### #5 — Port conflicts from ghost processes (Windows)
**What:** Every `uvicorn` restart on the same port failed with `[WinError 10048]`. Background processes from `Start-Process` survive shell session resets on Windows.  
**Fix:** Use incrementing ports (8010 → 8011 → 8020) or kill with `Get-NetTCPConnection | Stop-Process`.  
**Lesson:** On Windows, PowerShell `Start-Process -WindowStyle Hidden` leaves orphan processes. Always check ports before starting servers.

---

### #6 — `curl` on PowerShell is an alias for `Invoke-WebRequest`
**What:** `curl -H "Content-Type: application/json" -d '{...}'` fails — PowerShell's `curl` alias doesn't accept `-H` or `-d`.  
**Fix:** Use `Invoke-RestMethod -Uri ... -Method POST -ContentType ... -Body ...`  
**Lesson:** Always use native PowerShell cmdlets on Windows. Never assume Unix CLI tools work.

---

### #7 — Phoenix annotation write: `'span_id' and 'context.span_id' both present`
**What:** `log_span_annotations_dataframe()` failed when the DataFrame had both a `span_id` column (we added it) and `context.span_id` (already in the fetched df).  
**Fix:** Use only `context.span_id` as the column name. Phoenix expects this exact name and rejects duplicates.  
**Lesson:** Phoenix client has strict column name expectations. Don't rename or alias — use the canonical name from the returned DataFrame.

---

### #8 — `LLM(provider="google")` reads `GOOGLE_API_KEY`, not `GEMINI_API_KEY`
**What:** `phoenix-evals` `ClassificationEvaluator` with `provider="google"` raised `No API key provided` even though `GEMINI_API_KEY` was set.  
**Fix:** Aliased at import time: `os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")`. Also pass `api_key=` explicitly to `LLM()`.  
**Lesson:** `phoenix-evals` follows the Google GenAI SDK convention of `GOOGLE_API_KEY`. Document this clearly — it will catch every new user of the stack.

---

### #9 — SpanQuery filters (`span_kind`, `parent_id`) silently return empty
**What:** `SpanQuery().where("span_kind == 'LLM'")` and `SpanQuery().where("parent_id is None")` both returned empty DataFrames when called from Python, even though the same spans were visible in the UI and returned by an unfiltered fetch.  
**Root cause:** Unknown — possibly a Phoenix 20.14.0 / SpanQuery filter compilation bug on Windows with the gRPC transport. The unfiltered fetch worked every time.  
**Fix:** Fetch all spans unfiltered, then filter in Python with `df[df["span_kind"] == "LLM"]`.  
**Lesson:** Don't assume SpanQuery filter expressions work identically across Phoenix versions. Always have a Python-side fallback filter.

---

### #10 — `pandas 3.0` `groupby.apply()` returns Series-of-Series, not DataFrame
**What:** `df.groupby("context.trace_id").apply(pick_span)` where `pick_span` returns a `Series` (single row) produced a `Series` object in pandas 3.0, not a `DataFrame`. Calling `.reset_index(drop=True)` on it produced a 1-column DataFrame, losing all span columns.  
**Fix:** Replaced `groupby.apply` with a vectorised approach: compute `_row_idx`, use `groupby().max()` to find the last text-reply span per trace, then select rows by index.  
**Lesson:** Pandas 3.0 changed `groupby.apply` semantics for functions returning a Series. Vectorise instead of applying row-returning functions.

---

### #11 — google-genai instrumentor stores raw SDK HTTP blob, not parsed text
**What:** `attributes.output.value` in Phoenix traces contained the full raw Gemini SDK HTTP response JSON (`{"sdk_http_response": {...}, "candidates": [...]}`), not the agent's text reply. `attributes.llm.output_messages[N].message.content` was also empty for most spans.  
**Root cause:** `openinference-instrumentation-google-genai` stores the SDK response object verbatim, not the extracted text.  
**Fix:** Parse `candidates[0].content.parts[N].text` from the raw blob in `_extract_assistant_reply()`.  
**Lesson:** Always inspect what the instrumentor actually stores before writing eval extractors. Don't assume `output.value` = the model's text reply.

---

### #12 — All baseline spans were intermediate tool-call steps, not final replies
**What:** The baseline traffic run (`generate_traffic.py`) produced 73 spans, but all had `output_messages.message.content == ""` — they were the intermediate `generate_content` calls that returned `function_call` parts, not the final text replies. The final text-reply spans had `has_text=True` in their SDK blob but were not being selected.  
**Root cause:** Deduplication was keeping the first span per trace (wrong). Also, the earlier runs produced only tool-call spans because they all hit `MAX_STEPS` before producing a text reply.  
**Fix:** Changed deduplication to prefer the last span with a text reply (`_has_text_reply` check on `attributes.output.value`). Also deleted old runs that were all MAX_STEPS failures.  
**Lesson:** Multi-step agents produce multiple spans per conversation turn. The evaluable span is the one with a final text reply, not the first or last by time.

---

### #13 — Idempotency watermark via annotation column unreliable
**What:** After Cycle 1 wrote `tool_call_check` annotations to Phoenix, Cycle 2 still fetched 19 spans (same ones) because the annotation column didn't appear in the raw unfiltered `get_spans_dataframe()` response.  
**Root cause:** Phoenix only returns annotation columns when the fetch query specifically references them. Unfiltered fetches don't include annotation data.  
**Fix:** Local watermark file (`.scored_spans.json`) records scored span_ids. `mark_scored()` called in `run_evals` after each cycle. No Phoenix dependency for idempotency.  
**Lesson:** Don't rely on Phoenix returning annotation columns in raw span fetches for idempotency. Track scored spans locally or use a Phoenix dataset.

---

### #14 — LLM judge marked real fixture data as "ungrounded" (date confusion)
**What:** `groundedness` score was 0.07 (1/13) after Cycle 1. The judge explanation: *"flights cannot be searched more than 330 days in advance — the 2026 dates are too far in the future, so the agent fabricated everything."*  
**Root cause:** The judge had no context that the agent uses a local fixture dataset with pre-loaded 2026 data. It applied real-world booking system constraints.  
**Fix:** Added an `IMPORTANT CONTEXT` block to the groundedness prompt explaining the fixture data model.  
**Lesson:** LLM judges need domain context about the system under evaluation, not just the input/output. A judge calibrated for a real booking system will fail on a fixture-based demo agent. **This is also why human-labeled golden sets exist — to catch exactly this kind of judge miscalibration before it propagates.**

---

## Agent Bugs Found (Eval-Detected)

These are real defects in `agent/tools.py` caught by the eval loop.
Each will be fixed in P7 with a commit citing the eval that found it.

| Bug | Location | Eval that caught it | Effect |
|---|---|---|---|
| `search_flights` ignores direction — NY→Miami returns same flights as Miami→NY | `tools.py:search_flights` | `data_grounding_check` | Wrong flights shown |
| `search_flights` ignores `date` parameter entirely | `tools.py:search_flights` | `data_grounding_check` | Stale/wrong results |
| `search_hotels` ignores `check_out` — stay can extend past availability window | `tools.py:search_hotels` | `data_grounding_check` | Unavailable hotels shown |
| `get_weather` double-converts °F→°F (values already in °F, conversion applied again) | `tools.py:get_weather` | `data_grounding_check` (temp mismatch) | Wrong temperatures |
| `create_itinerary` uses `range(1, num_days)` — 5-day request returns 4 days | `tools.py:create_itinerary` | `param_match_check` | Off-by-one itinerary |
| System prompt has no current date → relative dates ("next Friday") unresolvable | `agent/prompt.py` | `tool_call_check` (MAX_STEPS) | Agent loops until MAX_STEPS |
| System prompt has no scope rule → agent answers visa/refund/currency questions | `agent/prompt.py` | `tool_call_check` (out-of-scope) | Fabricated out-of-scope answers |

---

## Stack Notes (for future builders)

- **Phoenix version:** 20.14.0 — SpanQuery filters unreliable, use Python-side filtering
- **google-genai:** 2.24.0 — `parameters_json_schema=` accepts Anthropic `input_schema` format directly
- **openinference-instrumentation-google-genai:** 1.4.7 — stores raw SDK blob in `output.value`, not parsed text
- **pandas:** 3.0.6 — `groupby.apply` with row-returning functions changed semantics; vectorise instead
- **phoenix-evals:** 3.8.0 — `LLM(provider="google")` reads `GOOGLE_API_KEY`; alias from `GEMINI_API_KEY` required
- **Windows gotchas:** `curl` = `Invoke-WebRequest`, ghost processes on ports, `load_dotenv()` needs explicit path

---

## Review Findings & Process Challenges (2026-09-20, after handoff review)

Issues found reviewing the P2-P8 scaffold. Defects themselves belong in Phoenix
(annotations + dataset); this section is for *lessons about the work*.

### #15 — Traces were flat: 1 LLM call = 1 trace
**What:** Phoenix showed 73 spans = 73 traces. Only auto-instrumented `GenerateContent` spans; no agent-turn span, no tool spans.
**Why it matters:** tool inputs/outputs only exist inside the *next* LLM call's input blob. Evals had to regex raw SDK JSON. Fallback replies (from our loop, not the model) produced no span at all, so the worst failures were invisible.
**Fix:** explicit `agent` span per user turn + `tool` span per tool call.
**Lesson:** auto-instrumentation traces the SDK, not your logic. Trace the seams your evals need.

### #16 — Judge never saw tool results
**What:** judge templates got only `{{input}}`/`{{output}}`. "Groundedness" = plausibility guess. Score 8% (artifact). Patch #14 told judge "fixture data is valid" → risks rubber-stamping.
**Fix:** feed tool outputs to the groundedness judge as reference context.
**Lesson:** groundedness needs a reference. No reference → not groundedness.

### #17 — Judge cache keyed on span_id only
**What:** editing judge prompt/model reuses old verdicts; Phoenix still showed the pre-patch 1/12 split.
**Fix:** cache key = hash(span_id + prompt + model).
**Lesson:** any cache in an eval loop must key on the evaluator version, or "improvements" silently don't apply.

### #18 — Deterministic checks failed open; 100% pass on known-buggy traffic
**What:** `data_grounding_check` only tested "flight number exists somewhere in fixtures" (not this call's output, no price/weather/direction). Regex could match "in 2026". Branches returned pass when unable to verify. 19/19 passed despite reversed-direction and off-by-one bugs.
**Lesson:** a 100% pass rate on traffic you know is broken = broken eval. Sanity-check evals against known defects before trusting them. Fail closed.

### #19 — Old "bugs caught by eval X" table was unverified
**What:** BUILD_LOG bug table credited checks that, per the scores, did not catch those bugs.
**Lesson:** don't record a defect as eval-detected until a run demonstrates it.

### #20 — Scope drift across sessions
**What:** after a mid-project tool switch, `evals/` grew to ~930 LOC (bound ~500), added local state files (watermark, violations.json), 3 scratch scripts.
**Lesson:** hard bounds must be re-read at every handoff; write them where the next agent sees them (plan file + repo doc), and audit LOC/state at phase exits.

### #21 — Repo `origin` is Arize's repo
**What:** clone's remote = github.com/Arize-ai/sample-travel-agent. Pushing goes to their repo. Deliverable needs a link to *our* codebase.
**Fix:** create own GitHub repo, repoint `origin`. Nothing pushed.

### #22 — Fallback/step-cap failures are behavior, not just infra
**What:** 4/23 baseline messages hit MAX_STEPS (relative dates, no-data cities): model retries tools with guessed dates. Original loop had no cap → infinite loop.
**Lesson:** a guardrail (step cap) converts a hang into a measurable failure — but only if the eval loop can see it (see #15).

### #23 — Reasoning tokens dominate cost
**What:** 18k of 25k completion tokens (71%) were Gemini reasoning tokens.
**Lesson:** cost dashboards must split reasoning vs output tokens; thinking budget is a cheap lever.

### #24 — Tool bug: `tools.py` reads data/*.json without `encoding="utf-8"`
**What:** on Windows the OS default encoding (cp1252) mangles accents: tool returns `Hotel LumiÃ¨re`; the model silently "repairs" it in its reply. Found because the judge's reference context showed mojibake.
**Impact:** any accented data is corrupted at the source; our own fixture loader had the same flaw and would have failed open on accented hotel names.
**Fix (P7):** `open(..., encoding="utf-8")` in tools.py. Evals now read fixtures as utf-8 and repair mojibake in captured tool results.

### #25 — Stale server on a reused port polluted the baseline
**What:** an old uvicorn from a prior session held port 8010 (`/health` still answered). New server failed to bind, traffic silently hit the OLD code and wrote 76 spans into the wrong Phoenix project.
**Lesson:** after starting a server, check its log for the bind line, not just `/health`. Use a fresh port per run. Phoenix/OTel import takes >8 s — poll `/health`, don't `sleep 8`.

### #26 — Multi-turn: per-turn checks false-failed follow-ups
**What:** "add a hotel for that weekend" reused hotel results the agent fetched proactively in the previous turn. Per-turn grounding said "no tool called / hotels not in tool results".
**Fix:** pool tool calls from earlier turns of the same session as context for tool_called, reply_grounded and the judge reference.
**Limit:** a follow-up that needs *new* data but reuses stale context would pass tool_called. Acceptable for the demo; noted for prod.

### #27 — Heredoc Python on Windows: source encoding bit us
**What:** `python - <<'E'` patch scripts that read/wrote UTF-8 files with the default encoding half-applied (em-dashes/degree signs didn't match).
**Lesson:** always `encoding="utf-8"` on Windows, or use the editor tool for non-ASCII edits.

### #28 — Judge now catches embellishment (the point of Stage 2)
**What:** with tool results as reference, the groundedness judge flags replies that add unsupported detail ("excellent reviews", "great views", neighborhood claims, invented airlines / a "330 day booking window" when search returned []). Stage 1 exact-match cannot see these.
**Lesson:** this is the concrete argument for two stages: exact checks for identity/price/route; a judge with a reference for semantic drift.

### #29 — Review-sheet bug: empty-list placeholder leaked into real data
**What:** `(no tools called)` was prepended to real tool results in golden.csv (reviewer thought no tool ran). Cause: a formatter returned a display placeholder for an *empty* list, and the caller concatenated two formatted parts.
**Fix:** formatter returns "" for empty; the caller inserts the placeholder only if *both* parts are empty. Re-verified: 0 leaks; only the 2 genuinely tool-less turns (visa, refund) show it.
**Lesson:** (1) keep display defaults at the outermost layer, never inside a helper that gets composed. (2) A human reviewer caught this by reading the artifact — human review of eval inputs is part of the method. (3) Repeat of #27: heredoc-patched edits silently no-op'd; always re-read/verify after patching, prefer the editor tool.

### #30 — Judge v1 vs human labels: groundedness 47% (kappa -0.03), tone 94% raw / kappa 0.00
**What:** 17 labeled rows. Groundedness: 9 disagreements — 7 where judge is stricter (descriptive hotel/flight embellishment: "close to Times Square", "great views", "nonstop", airport codes), 2 where judge is more lenient (out-of-scope visa/refund answers; template scoped "source of truth" to flights/hotels/weather so judge allowed general knowledge). Tone: judge said "professional" for all 17; human flagged 1 (refund reply) -> raw agreement hides zero discriminating power (kappa 0).
**Lesson:** (1) the rubric — not the model — is the first thing to calibrate; humans and judge drew the "embellishment" line in different places. (2) report kappa, not just raw agreement: with 16/17 one-class labels, 94% is meaningless. (3) once a labeler has seen the judge's disagreements the labels are no longer blind — record which round is which.

### #31 — Calibration round 2: judge v2 rubric -> groundedness 89% (kappa 0.79)
**What:** after the human chose the "hard facts only" rubric (names, prices, ratings, times, dates, availability, route attrs like nonstop/airport codes, weather = must match tools; subjective color and pleasantries = fine; capability claims / authoritative out-of-scope facts = ungrounded), judge template v2 + 4 label adjudications (rows 2, 8 -> ungrounded; row 18 tone -> professional; row 19 typo). Groundedness 17/19 = 89%, kappa 0.79. Tone 19/19 but kappa is undefined-ish (all labels one class).
**Caveats to state honestly:** (1) round 2 was adjudicated AFTER seeing round-1 disagreements — not blind; round-1 labels kept in golden_round1_blind.csv. (2) n=19 is tiny; treat 89% as "calibrated on this set", not a population estimate. Plan: label fresh post-fix traffic as a hold-out. (3) Tone judge never saw an unprofessional reply, so its sensitivity is untested. (4) 2 remaining disagreements (rows 9, 13) are hard-fact claims ('beachfront', 'direct') the human labeled grounded — left as-is rather than tuning labels to hit a number.
**Lesson:** the calibration loop (measure -> inspect disagreements -> decide the rubric with the domain owner -> update template -> re-measure) is the deliverable, more than the final number.

### #32 — Experiment v1-fixed vs v2-fixed (tools identical, prompt only variable)
**Setup:** travel-agent-baseline (broken tools+v1) -> travel-agent-v1-fixed (fixed tools+v1) isolates tool-fix impact; travel-agent-v1-fixed -> travel-agent-v2-fixed (fixed tools+v2) isolates prompt impact.
**Result:** fallback turns 4->1, groundedness (judge) 38%->100%, reply_grounded 88%->100%, tool_called 78%->91%, tokens 123k->67k (~45% cheaper: fewer retries/fallbacks). tone regressed 100%->76%.
**Regression root cause:** v2's honesty-on-empty-results instruction told the model the "why" (demo system, fixed test data) as reasoning context; model started saying that directly to users ("Since this is a demo system with a fixed set of test data...") — exactly the internal-systems leak another prompt line already banned. One-line fix: made explicit that fact is for internal reasoning only, never to be said to the user. Verified on the exact triggering query — leak gone.
**Second finding (not a prompt bug):** 2 of 5 tone flags were create_itinerary's placeholder content ("Explore {city} / Activities / free time" x N) read verbatim, now that the day-COUNT bug is fixed and the content is fully visible/legible. The count fix (#which commit) was correct and necessary; it also unmasked a pre-existing content-quality limitation in the tool (out of scope to fix — it's a stub with no real per-destination data). Logged as a known limitation, not an eval-loop defect.
**Judge-calibration note:** 1 of 5 tone flags ("no flights found, try different dates" marked "dismissive") looks like an overly strict judge call, not a real tone problem — same polite decline pattern was approved as professional in golden-set calibration (#31). Left as-is; would revisit if it recurs at scale.
**Loop-order verification:** queried Phoenix directly (not just code review) on travel-agent-v1-fixed: 7 turns failed the Stage-1 gate, 0 of them carry any LLM-judge annotation; for every turn with both annotation kinds, last CODE annotation timestamp <= first LLM annotation timestamp. Confirms the gate->judge order is enforced in practice, not just asserted by reading run_evals.py.
