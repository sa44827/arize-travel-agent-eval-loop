# Demo Walkthrough — Interview 2 Script

Click-by-click script for the live portion of the Arize FDE solution presentation.
Built around what's actually running: Phoenix OSS at `localhost:6006`, the agent via
its Swagger UI at `localhost:8000/docs`, and the real Phoenix projects produced by
this build (see `docs/BUILD_LOG.md` for the full evidence trail behind every claim
made here).

Time budget assumes a 1-hour session with ~35 min of live/narrated demo and the rest
on the deck + Q&A. Adjust live.

## Phase 0 — Before you start (prep, not live, ~5 min)

1. Start Phoenix: `phoenix serve`. Confirm `localhost:6006` loads in a browser.
2. Start the agent: `uvicorn agent.api:app --port 8000` (check nothing else already
   owns port 8000 first — a stale server on a reused port silently ate a whole
   traffic run earlier in this build; see `docs/BUILD_LOG.md` #25).
3. Open two tabs: Swagger (`localhost:8000/docs`) and Phoenix (`localhost:6006`).
4. Keep `docs/BUILD_LOG.md` open on your own screen (not shared) as a cheat sheet
   for exact numbers.
5. Note: the agent runs on `gemini-3.5-flash`, a separate quota from the judge model
   (`gemini-3.1-pro-preview`). The live agent demo works regardless of judge-quota
   state. Only the Stage-2 (LLM-judge) portions of Phase 2 depend on judge quota.

## Phase 1 — Agent Demonstration (~8 min)

**Where:** Swagger tab, `POST /chat`.

1. Click `POST /chat` → "Try it out."
2. Paste a real query:
   `{"message": "Find me a flight from New York to Miami on March 12, 2026."}` → Execute.
3. Point at the response: real flight numbers, real prices. Say plainly: *"these come
   from the tool, not the model's imagination — we'll prove that in Phase 2."*
4. Take the `conversation_id` from the response, paste it into a second call:
   `{"message": "Which one is cheapest?", "conversation_id": "<paste>"}`. Shows
   multi-turn — the agent correctly picks the cheapest from what it just found.
5. **Best single demo moment — show honesty on an empty result:**
   `{"message": "Find me a flight from Denver to Tokyo on August 14, 2026."}` (no
   such route exists in the fixtures). The agent says nothing was found instead of
   inventing one. Say: *"Earlier in this build, the unmodified agent invented an
   airline and a fake '330-day booking window' explanation here. That's fixed now —
   we'll show exactly how we caught it."*
6. **Show the scope guardrail:**
   `{"message": "Do I need a visa to visit Japan?"}` → politely declines, in scope
   only. Ties directly to the client's own words (customer discovery transcript,
   [12:47]): *"we don't want the general public abusing it just for tokens to go
   solve math problems."*

## Phase 2 — Automated Feedback Loop (~20 min, the core of the interview)

### 2a. Tracing — one trace = one turn (~5 min)

**Where:** Phoenix tab → project `travel-agent-baseline` → Traces view.

1. Click any trace row. Point at the hierarchy: **`agent_turn`** (root, AGENT kind)
   → its children: one or more **`GenerateContent`** (LLM kind) and, if tools were
   called, **TOOL**-kind spans named `search_flights` / `search_hotels` / etc.
2. Click a TOOL span. Show its **input** (the exact args the model passed) and
   **output** (the exact JSON the tool returned). Say: *"This is why our
   deterministic checks can be exact — we're comparing the reply against the
   literal data the tool returned for this call, not guessing."*
3. Click the `agent_turn` root span, scroll to attributes, point at
   `agent.fallback: false`. Explain: *"Every turn carries a flag for whether it
   hit our safety cap and gave up. We can query for these directly — it's how we
   caught the model looping on unresolvable relative dates."*
4. Switch to **Sessions** view (left nav). Point out session count vs. trace count
   differ (23 traces, 22 sessions). One-sentence explanation: *"a trace is one
   turn, a session is the whole conversation — this is how the multi-turn 'add a
   hotel to that' follow-up groups with its earlier turn."*

### 2b. The two-stage eval, proven in order (~5 min)

**Where:** same trace, scroll to its **Annotations** panel (below the span detail).

1. Point at annotations named `tool_called`, `reply_grounded`, `tool_contract` —
   `annotator_kind: CODE`. Say: *"Stage 1, deterministic, free."*
2. Find a trace that also has `groundedness`, `tone` — `annotator_kind: LLM`. Say:
   *"Stage 2, only runs if Stage 1 passed — that's the cost gate."*
3. **The proof, not just the claim:** *"We verified this isn't just intended, it's
   enforced. Of the turns that failed Stage 1 in a real run, zero carry any Stage 2
   annotation — checked directly against Phoenix's data, not by reading our own
   code."* (`docs/BUILD_LOG.md` — the gate/judge ordering verification.)

### 2c. What the loop actually found and fixed (~5 min)

**Where:** narrate from `docs/BUILD_LOG.md`; optionally show the commit list on
GitHub (`eval-loop` branch).

1. Show the baseline vs. fixed numbers (table below). Every fix traces to a
   specific commit citing the violation that caught it — open one
   (e.g. "search_flights ignored travel direction") to show the commit message
   names the exact eval and finding.
2. **The regression story — strongest "this loop actually works" evidence:**
   *"While building the fix, our own prompt change introduced a NEW bug — it
   started telling users 'this is a demo system with fake data,' which is exactly
   the internal-systems leak we were trying to prevent elsewhere. The same eval
   loop caught that, same day, on our own change."*

### 2d. Judge calibration (~3 min)

**Where:** narrate; optionally open `evals/golden/golden.csv` and
`golden_round1_blind.csv` side by side.

1. State plainly: *"We didn't just assert the judge is trustworthy — we measured
   it against human labels."*
2. Numbers: **47% agreement on the first blind pass — essentially no better than
   chance (Cohen's kappa −0.03).** Root cause: the judge and the human drew the
   line on "embellishment" in different places.
3. *"We didn't change the labels to fit the judge — we calibrated the rubric with
   the domain owner, then re-measured: 89% agreement, kappa 0.79."* Best "systems
   thinking" moment in the demo — say it slowly.

### 2e. Automation running unattended (~2 min)

**Where:** terminal, or narrate if judge quota is tight that day.

1. If quota allows live: start `python -m evals.scheduler`, send one new message
   via Swagger, and within the interval show the new turn getting a `gate`
   annotation without touching anything else.
2. If narrating instead: *"We ran this unattended earlier — seeded 23 turns, sent
   2 more mid-run through the live API, and confirmed the scheduler picked them up
   automatically. We also found and fixed a real reliability bug live: when the
   judge model's daily quota was fully exhausted, the whole cycle crashed instead
   of degrading gracefully. We fixed it so a Stage-2 outage never discards Stage
   1's free results, and verified the fix on the next cycle."* Turns a quota
   problem into a production-readiness talking point.

## Phase 3 — Production Readiness (~10 min, talking points not live)

- **Async pattern**, justified by their own words (transcript [33:40]): *"nothing's
  worse than talking with a chatbot and waiting five minutes for a response."*
- **Cost gate**, justified by their own words (transcript [41:43]–[41:58]): *"less
  the scale of users, more so scale of cost... how can we counteract that?"*
- **Cost split**, per their explicit ask (transcript [18:59]–[19:10]): agent tokens
  and judge/eval tokens are tracked as two separate numbers, in two separate
  Phoenix projects (`<project>` vs `<project>-evals`).
- **Silver/Gold simplification** — one-liner if asked: *"Phoenix already stores
  clean results as annotations and computes rollups on demand; at higher volume,
  that's exactly the layer Arize AX's managed store and continuous monitors take
  over."*
- **Reliability/rollback** = git: one commit per fix, each reversible with a
  `git revert`; prompt v1 kept byte-for-byte alongside v2 specifically so a
  rollback is a config flip (`PROMPT_VERSION=v1`), not a rewrite.

## Phase 4 — Results & Learnings (~7 min)

1. Before/after table (below).
2. Honest "what we didn't build and why" — design-only items: continuous
   streaming at scale, auto-PR generation, SNS alerting, RBAC, the scope-guardrail
   classifier, judge tiering/sampling.
3. Close with the retry-cap gap as the "what I'd do next" — a turn only clears the
   gate on a *complete* judge pass in one cycle, so partial-quota conditions cause
   indefinite reprocessing instead of convergence. Fix = capped retries + a
   `judge_unavailable` state. Naming a known limitation you didn't fix, with the
   fix already designed, reads as more senior than pretending everything's done.

---

## Numbers to have memorized (all real, all sourced in `docs/BUILD_LOG.md`)

| | Baseline | v1-fixed (tools only) | v2-fixed (+ prompt) |
|---|---|---|---|
| Fallback turns | 4/23 | 4/23 | 0/23 |
| `tool_contract` | 35% | 100% | 100% |
| Groundedness (judge) | 17% | 38% | 91% |
| Judge agreement w/ human | — | 47% → 89% after calibration | — |

## Fallback if something breaks live

- **Phoenix won't load:** it's been known to silently stop between sessions with no
  error surfaced (`docs/BUILD_LOG.md` #34, tracing fails silently by design). If it
  happens live, don't panic-debug on camera — narrate from the numbers above and
  `docs/BUILD_LOG.md` instead, and offer to show the actual Phoenix UI on a follow-up.
- **Judge quota exhausted:** expected and already a talking point (Phase 2e). Don't
  apologize for it — it's real infra behavior worth discussing, not a demo failure.
- **Port conflict on agent startup:** use a different port (`--port 8001`), update
  the Swagger URL accordingly.
