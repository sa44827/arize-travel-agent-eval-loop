# Readiness Summary — Arize FDE Solution Presentation

Master verification document. Written to stand alone: paste this into a fresh Claude
session with zero other context and it should be enough to sanity-check the whole
project before presenting. It consolidates two independent review passes
(customer-alignment review, scope/over-engineering review) plus the orchestrator's
fixes applied afterward, verified directly against current source files rather than
taken on faith.

---

## 1. What this project is

This is the solution deliverable for an Arize Forward Deployed Engineer interview
loop: build a simple AI agent (a travel-itinerary assistant) and an automated
feedback loop around it — tracing, evaluation, automation, and production-readiness
thinking — then present it back to a simulated customer team. The brief explicitly
de-emphasizes the agent's own sophistication ("a simple agent with a strong feedback
loop is preferred over a complex agent with weak observability" —
`docs/arize_interview_screen.md`) and grades the eval loop, the production-readiness
story, and the ability to translate customer requirements into a working system.

## 2. What was built

- **The agent:** a plain Gemini tool-calling loop (ported from an Anthropic-based
  sample repo) with four tools — `search_flights`, `search_hotels`, `get_weather`,
  `create_itinerary` — over a fixture dataset. Deliberately simple; the loop around
  it is the point.
- **Tracing:** explicit `agent_turn` (AGENT) and `tool` (TOOL) spans added by hand,
  because auto-instrumentation only traced raw SDK calls and hid tool inputs/outputs
  (BUILD_LOG #15). This is what lets Stage-1 checks be exact instead of regexing a
  raw response blob.
- **Two-stage eval architecture:** Stage 1 is a free, deterministic gate
  (`tool_called`, `reply_grounded`, `tool_contract`) that fails closed (unable to
  verify = fail, never a silent pass, per the #18 fix). Stage 2 is an LLM-judge
  (`groundedness`, `tone`, `itinerary_accuracy`) that only runs on turns that pass
  Stage 1 — verified directly against Phoenix's own annotation data, not just
  asserted from code: of the turns that failed Stage 1 in a real run, zero carry any
  Stage 2 annotation (BUILD_LOG #32).
- **Real defects found and fixed (7 total):** 5 tool bugs — `search_flights` ignoring
  travel direction, `search_flights` ignoring the `date` parameter, `search_hotels`
  ignoring `check_out`, `get_weather` double-converting °F, `create_itinerary`'s
  off-by-one day count — plus a non-UTF-8 file read that mangled accented characters
  (#24), plus one prompt regression the team introduced itself while fixing things
  (v2's honesty instruction leaked "this is a demo system with fake data" to users,
  caught by the same eval loop same day, #32), plus one reliability bug in the eval
  loop's own crash handling under judge-quota exhaustion (#37).
- **Judge calibration, measured not assumed:** round 1 (blind human labels vs. judge)
  = 47% agreement, kappa −0.03 (no better than chance). Root-caused to the judge and
  human drawing the "embellishment" line differently. Rubric recalibrated with the
  domain owner; round 2 = 89% agreement, kappa 0.79, on a 19-turn golden set
  (BUILD_LOG #30, #31).
- **Controlled experiment isolating tool-fix vs. prompt-fix impact:** baseline →
  tools-fixed-only → tools+prompt-v2, same 23 test conversations at each stage.
  Clean rescored numbers (#33): fallback turns 4→4→0, `tool_contract` 35%→100%→100%,
  groundedness (judge) 17%→38%→91%, tone 100%→(n/a)→77% (tone regression
  root-caused to 3 separate, already-diagnosed causes, not one bug).
- **Cost split, per the client's explicit ask** ("being able to monitor how much
  we're spending on evaluating and how much we're actually spending on agents" —
  transcript [18:59]): agent tokens and judge tokens traced to two separate Phoenix
  projects (`<project>` vs `<project>-evals`, BUILD_LOG #36). Real dollar figures on
  the `cost-eval` slide: at 1M conversations/day, the Stage-1 gate (only ~30% of
  turns reach the paid judge) saves an estimated ~$1,990/day / ~$727,000/year versus
  judging every turn, using Gemini 3.1 Pro's published rate ($2/M input, $12/M
  output). The slide is explicit that this is a projection from one measured
  per-check cost, not from a million live requests — stated honestly, not implied as
  live production data.
- **Automation proof:** `evals/scheduler.py` run unattended for a real interval,
  seeded 23 turns, 2 more sent live mid-run via the API, confirmed picked up
  automatically on the next cycle with no manual trigger (BUILD_LOG #37).
- **Scope discipline:** `evals/` totals 545 LOC across 6 files (Agent 3's
  measurement), matching the ~500-line/6-module target after an earlier scope-drift
  incident (#20) was caught and corrected. No local state files exist — idempotency
  is via a Phoenix annotation ("graded" tag) written onto each turn's own span, not a
  file on disk (confirmed both in BUILD_LOG #35's Silver/Gold-as-annotations design
  and directly in the current `automation.html` / `prod-readiness.html` slide text).

## 3. Customer alignment

Recreated from Agent 2's requirements-traceability review (verbatim findings, per
the orchestrator's brief), updated to reflect fixes applied since that review. Each
row was originally checked by Agent 2 against a transcript quote and the actual
BUILD_LOG/code — that verification is treated as already done, not re-derived here.

| Requirement (transcript source) | Status | Note |
|---|---|---|
| Correctness (parameters match request) | BUILT | Stage-1 `tool_contract` / `reply_grounded` checks; caught real bugs (direction, date, off-by-one) |
| Groundedness (real, available flights/hotels) | BUILT | Stage-1 exact match + Stage-2 judge with tool-output reference; measured 17%→91% |
| Tone (professional, public-facing) | BUILT | Stage-2 `tone` judge; calibration caveat below — judge has never seen an unprofessional reply |
| Scope / relevance (stay on travel topic) | PARTIALLY BUILT | Agent-side: built and demoed (declines visa/refund/math questions live). Monitoring/eval side: MISSING — no dedicated check watches for scope drift over time. `prod-readiness.html` now states this split explicitly rather than reading as "nothing was done" |
| Alerting / thresholds (ASAP notification on breach) | PARTIALLY BUILT | Per-metric thresholds computed and checked (`evals/thresholds.py`); breach today is logged/printed, not routed to a person — paging is DESIGN-ONLY |
| Cost split (agent vs. eval spend, tracked separately) | BUILT | Two Phoenix projects; real $/day projection on `cost-eval.html` |
| Modularity (reusable across future agents) | DESIGN-ONLY / ASSERTED, NOT DEMONSTRATED | The loop's shape (trace → gate → judge → annotate → threshold-check) has no travel-specific logic in `run_evals.py`/`scheduler.py`/`thresholds.py`; travel-specific logic is isolated to `deterministic.py` and `judges.py`. This is a real structural argument, but no second agent was actually run through the loop — voice it as a design principle, not proof, per Agent 2's finding |
| Availability (agent never blocked on eval) | BUILT | Structural: agent replies synchronously; eval loop reads Bronze (persisted traces) out of band — no code path where a user waits on an eval |
| Business metrics (conversion rate, live-support deflection) | NOW ADDRESSED (was the single biggest gap Agent 2 found) | New `business-outcomes.html` slide connects eval scores to both metrics with the transcript quote, and is explicit that there is no conversion baseline yet — that follow-up belongs to the client (An Nguyen), per the transcript's own next-steps |
| Human-reviewed feedback loop (draft PRs, human approves) | DESIGN-ONLY, correctly scoped | Auto-PR generation not built; explicitly matches the client's own stated preference for a human review step before merge (transcript [24:26]–[24:49]) — this is a case where NOT building something is the right call, not a gap |
| Continuous evals | BUILT | Scheduler runs unattended on an interval, verified picking up new traffic without manual triggering |
| Team onboarding (many members understand evaluators) | NOT DIRECTLY ADDRESSED | No dedicated slide/artifact for this; BUILD_LOG's own documentation and the per-metric threshold reasoning in code are the closest existing artifacts |

Agent 2's overall verdict (carried forward, not re-derived): the deck is honest,
does not rubber-stamp, and every "BUILT" claim checked out against BUILD_LOG/code.

## 4. Scope discipline

Agent 3's findings (verbatim, per the brief), with the one concrete issue verified
fixed:

- `evals/` is 545 LOC across 6 files — matches the ~500-line/6-module target.
- No local state files exist (confirmed by direct search) — idempotency is
  Phoenix-annotation-based only.
- Git history is one-fix-per-commit, as claimed.
- No speculative abstraction found in the eval modules.
- **The one real problem Agent 3 found:** both `automation.html` and
  `prod-readiness.html` claimed idempotency worked via "a local watermark" — factually
  wrong (the real mechanism is a Phoenix annotation; no local file exists), and it
  contradicted the project's own proudest design decision (no local state,
  BUILD_LOG #35).
- **Verified fixed by this review:** both files now describe the annotation-based
  mechanism accurately. `automation.html`: "no local file, that tag itself is the
  record, so nothing gets re-scored or re-billed." `prod-readiness.html`: "Idempotent
  scoring via the 'graded' tag written on each turn — no local state file, no
  re-billed re-scoring." Neither file mentions a watermark or a local file anymore.

Worth noting for calibration: BUILD_LOG entry #13 itself still describes an earlier,
now-superseded design (a local `.scored_spans.json` watermark file) as a historical
record of what was tried at that point in the build — that's an accurate log entry
about a rejected approach, not a live claim, and doesn't need correcting. The actual
current mechanism is documented in #35 and now correctly reflected in the deck.

## 5. Known gaps and open risks, ranked by severity

1. **RESOLVED — judge re-validated live with real quota (BUILD_LOG #44, #45).**
   User raised their Gemini key's rate limit; confirmed genuinely available (6/6
   sequential calls, not a single lucky ping). Re-running `scripts/validate_judge.py`
   surfaced a real, previously-invisible regression: the tone judge's earlier
   date-awareness fix had a clause ("factually confused about dates") that started
   firing on nearly every turn as real wall-clock time moved past the golden set's
   fixture dates — tone collapsed to 26% agreement. Root-caused and fixed (that
   clause never belonged in tone — it's about *how* something is said, not date
   validity, which is groundedness's job). Re-validated clean: **groundedness 89%
   agreement / kappa 0.79** (matches the original number exactly — genuinely
   confirmed, not assumed), **tone 100% agreement / kappa 1.00**. Also added a
   synthetic negative-class test (`evals/golden/tone_negative_examples.csv`) since
   the real golden set had zero unprofessional examples — tone judge caught 4/4.
   The 89% groundedness / 100% tone figures can now be presented as live-validated,
   current-template numbers, not pre-fix ones.
2. **Partial-quota retry convergence gap (BUILD_LOG #37, unfixed).** A turn only
   clears the gate once it gets a *complete* judge pass (groundedness AND tone) in
   the same cycle. Under partial-quota conditions (some calls succeed, some 429),
   this causes indefinite reprocessing of the same turns rather than convergence —
   observed directly (cycle 2 reprocessed the same 24 turns cycle 1 had partially
   judged). Production fix is designed (capped retries + a `judge_unavailable`
   state) but not built. This is disclosed as a known gap on both `automation.html`
   and `prod-readiness.html`.
3. **Scope-monitoring gap.** The agent declines out-of-scope questions in the live
   demo (built, works), but there is no dedicated eval/monitor watching for scope
   drift over time in production. This is the one secondary discovery requirement
   not fully placed in the loop. Now stated explicitly as a split (agent-side
   built/demoed vs. monitoring-side gap) on `prod-readiness.html`, per the fix
   applied after Agent 2's review.
4. **Modularity claim is asserted, not demonstrated.** The structural argument
   (travel-specific logic isolated to two files; the rest of the pipeline is
   domain-agnostic) is real and inspectable in the code, but no second agent was
   ever actually run through the loop to prove it. Voice this as a design principle
   under questioning, not as proof.
5. **Judge calibration was measured on 19 turns, once.** Both the original
   calibration report (BUILD_LOG #31) and Agent 2's review flag this: enough to
   calibrate a rubric, not to certify a population estimate, and the tone judge in
   particular has never seen an actually unprofessional reply, so its sensitivity is
   untested rather than merely uncalibrated (`prod-readiness.html`'s own "Known gap"
   column says this directly).
6. **Business-metrics connection has no baseline.** The new `business-outcomes.html`
   slide correctly connects eval scores to conversion rate and live-support
   deflection, but there is no actual conversion-rate baseline to compare against —
   the transcript itself records that follow-up as owed by the client (An Nguyen),
   not something this build could have produced.
7. **Cost projection is a projection, not measured live traffic.** The
   $1,990/day / $727,000/year figure on `cost-eval.html` is explicitly labeled as
   extrapolated from one real measured per-check cost, not from a million real
   requests. The slide states this itself — it is not a hidden caveat, just worth
   having the honest framing ready if pressed.
8. **Auto-PR generation, live paging, judge tiering/sampling, a real secrets
   manager, RBAC, and streaming at scale are all design-only**, by explicit
   client-informed choice in most cases (e.g., auto-PR: the client explicitly wants
   a human to review before merge, transcript [24:26]–[24:49]) or reasonable
   time-boxing in others. These are correctly labeled "designed, not built" across
   `prod-readiness.html` and `tradeoffs-close.html` — not gaps to apologize for, but
   worth knowing which is which if asked to justify any specific omission.

## 6. Deck structure (16 slides, in order)

1. **cover** — Title slide: "An automated feedback loop for a production travel
   agent." States the one-line thesis (simple agent, strong eval loop, evidence it
   caught real defects including a self-introduced one) and names restraint as a
   deliberate design signal.
2. **agenda** — Four sections matching the interview brief's own structure: agent
   demonstration, automated feedback loop, production readiness, results & learnings.
3. **problem** — The customer's own words (three verbatim transcript quotes on
   correctness/groundedness, availability, and cost-at-scale), plus a today-vs-wanted
   summary of the discovery call.
4. **architecture** — Live path (User → Agent → Tools → sync reply) vs. async eval
   loop (Bronze → Gate → Judge → Silver → Gold), with a Phoenix-OSS-now /
   Arize-AX-later framing.
5. **agent-demo** — The four tools table and the live-demo setup (Swagger UI):
   real query, multi-turn follow-up, an empty-result honesty case, and the
   out-of-scope decline.
6. **eval-method** — Stage 1 (deterministic, free, fails closed) vs. Stage 2
   (LLM-judge, gate-passers only), with the "17 of 23 judge calls never happened"
   cost-lever number.
7. **thresholds** — The six per-metric pass-rate targets (95/95/90/90/90/85%) and
   the reasoning for each, directly answering the client's invitation for a
   recommendation rather than a rubber-stamped 85–95%.
8. **tracing** — The `agent_turn` → `GenerateContent` → `search_flights` span
   hierarchy; trace-vs-session distinction (23 traces, 22 sessions); the
   gate-before-judge order verified against real Phoenix data (0 Stage-2 annotations
   on Stage-1 failures).
9. **calibration** — The 47%→89% judge-calibration story (kappa −0.03 → 0.79),
   framed as a measured claim, not an assumed one.
10. **automation** — What runs automatically (scheduler, gate, judge, tagging) vs.
    what stays human (fixing, committing, re-verifying), with the P8 unattended run,
    the live-caught crash, and the known partial-quota gap.
11. **results** — Baseline → tools-fixed → +prompt-v2 table (fallback, tool_contract,
    groundedness, tone), with the tone regression framed as the strongest evidence
    the loop actually works (it caught the team's own bug).
12. **business-outcomes** — Connects eval scores to conversion rate and live-support
    deflection (the client's stated business success metrics), with an honest
    no-baseline-yet caveat.
13. **cost** — Real dollar headline: $0.0165 → $0.0077 per conversation (54% cheaper
    after the fix), plus a $/day table at 1K / 100K / 1M conversations/day
    ($16,458/day → $7,653/day at 1M). All from real measured tokens at Gemini 3.5
    Flash's published rate, not a guess. (Note: this slide's file existed locally
    with these figures but was not actually published until this final pass —
    confirm by opening the live artifact, not just this summary, if in doubt.)
14. **cost-eval** — The dollar-figure version: ~$1,990/day / ~$727,000/year projected
    savings from the Stage-1 gate at 1M conversations/day, explicitly labeled as a
    projection from one measured rate.
15. **prod-readiness** — Three-column Built / Designed-not-built / Known-gap-unfixed
    breakdown, each item citing its BUILD_LOG entry.
16. **tradeoffs-close** — Final Built / Designed-not-built / Known-not-fixed summary,
    closing thesis line, and the GitHub link.

## 7. Pre-interview checklist

Concrete, actionable items — see `docs/DEMO_WALKTHROUGH.md` for the full click-by-click
script and `docs/ANTICIPATED_QA.md` for the full rehearsed Q&A bank; this list is
what to do with them, not a restatement of their content.

- [ ] Run through `docs/DEMO_WALKTHROUGH.md` live at least once end-to-end (Phoenix +
  agent both running, ports free) before presenting — confirm the exact Swagger
  calls in Phase 1 still produce the expected honesty/decline behavior.
- [ ] Confirm Phoenix is actually running and `travel-agent-baseline` /
  `travel-agent-v1-fixed` / `travel-agent-v2-fixed` / `travel-agent-automation-demo`
  projects are present with the expected span counts before trusting the demo not to
  silently fail (Phoenix has gone down silently before, BUILD_LOG #34).
- [ ] Have a fallback narration path ready for both "Phoenix won't load" and "judge
  quota exhausted" — both are pre-planned in `DEMO_WALKTHROUGH.md`'s "Fallback if
  something breaks live" section; rehearse saying them calmly, not apologetically.
- [x] Judge re-validated live (BUILD_LOG #44, #45): groundedness 89%/kappa 0.79,
  tone 100%/kappa 1.00, tone negative-class 4/4. These are now real, current numbers
  — safe to cite directly if asked.
- [ ] Walk through `docs/ANTICIPATED_QA.md` once, out loud, especially the
  "Curveballs" section (bigger model instead of evals, fixture-data cheating,
  modularity-as-a-claim, "what don't you know").
- [ ] Memorize the numbers table in `DEMO_WALKTHROUGH.md` (fallback 4/23→0/23,
  tool_contract 35%→100%, groundedness 17%→91%, judge agreement 47%→89%) so they can
  be stated without opening notes.
- [ ] Double-check the GitHub repo (`sa44827/arize-travel-agent-eval-loop`,
  branch `eval-loop`) is actually pushed and the link in `tradeoffs-close.html`
  resolves — this is the one deliverable (link to codebase) that fails silently if
  forgotten.
- [ ] If time allows, do one more read-through of `business-outcomes.html` and
  `thresholds.html` in the live artifact (not just this summary) since they are the
  two newest slides and haven't been demo-rehearsed as many times as the rest.

## 8. Links

- **Deck (live artifact):** https://claude.ai/artifact/EdmxUXEXB5LnzawC2CyG3M
- **Codebase:** github.com/sa44827/arize-travel-agent-eval-loop, branch `eval-loop`
- **`docs/BUILD_LOG.md`** — the full numbered build log (39 entries + Process &
  Collaboration Learnings); primary evidence source for every number and fix cited
  in this document and in the deck.
- **`docs/customer_discovery_transcript.md`** — verbatim mock customer discovery
  call transcript; ground truth for every requirement and quote used in the deck.
- **`docs/arize_interview_screen.md`** — the original candidate project brief
  (interview loop structure, deliverables, evaluation criteria).
- **`docs/DEMO_WALKTHROUGH.md`** — click-by-click live demo script for Interview 2,
  with timing budget, exact Swagger calls, and a memorized-numbers cheat sheet.
- **`docs/ANTICIPATED_QA.md`** — rehearsed Q&A bank organized against the brief's
  own "what we are evaluating" criteria, including deliberately skeptical/curveball
  questions.
- **`docs/READINESS_SUMMARY.md`** — this document.
