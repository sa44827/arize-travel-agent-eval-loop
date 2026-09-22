# Arize FDE — Travel Agent Eval Loop: Build Context

> **Purpose of this file.** This is the complete context handoff for building the
> Arize Solution Presentation demo. It seeds a fresh Claude Code session on the
> `sample-travel-agent` repo with everything agreed in the design phase: the
> client requirements, the architecture, the eval methodology, and the
> build-vs-design scope. Drop this in the repo root (rename to `CLAUDE.md` if you
> want Claude Code to auto-load it) and point the new session at it before
> building.
>
> **Read this first, then build. Do not re-derive the design — it's settled.**

---

## 1. The situation

- **Who:** Sharan — IBM tech consultant (NYC), background in GraphRAG / knowledge
  graphs / multi-agent orchestration. Interviewing for **Forward Deployed
  Engineer at Arize AI**.
- **Round:** Solution Presentation (round 2), next Wednesday. Round 1 (customer
  discovery) is done and passed.
- **The task:** Arize gave a sample travel agent repo. Build an **evaluation
  loop around it** and present: (1) the architecture/design with justified
  choices, (2) a **working demo** of the eval loop, (3) a production-readiness /
  scale story, (4) results & learnings.
- **The mock client (from discovery):** a travel company rolling out a
  public-facing agent that recommends **itineraries** (Phase 1 — no bookings
  yet). Stakeholders: **Nick** (head of product / Americas solutions lead),
  **PM** (main counterpart), **Sophia** (VP Eng / FDE — *her team reviews &
  merges the PRs*).

## 2. Guiding principle (do not violate)

> **Build the core loop. Design-and-justify everything else.**

A simple agent + strong feedback loop beats a complex agent + weak
observability. We are NOT over-engineering for millions of users. We build a
working core loop in Phoenix and *speak to* how the rest scales. Restraint is
the signal being tested — knowing what NOT to build is the senior move.

## 3. Product decision: Phoenix (build) → Arize AX (production)

Both are the same platform at different scale; anything built in Phoenix
lifts-and-shifts to AX. Same tracing (OTel/OpenInference), same eval SDK.

| | **Phoenix** (what we BUILD) | **Arize AX** (production recommendation) |
|---|---|---|
| Hosting | Self-hosted, local, free | Fully managed SaaS, auto-scaling |
| Storage | Stores traces locally (you operate it) | Managed hosted store (Arize operates it) |
| Evals | Same primitives; we orchestrate runs | Continuous/online evals scheduled automatically |
| Alerting | DIY | Built-in monitors + alerting |
| Multi-user | Single instance | Orgs/spaces/RBAC (onboard many evaluators) |
| Cost | Token data on spans; roll up yourself | Cost dashboards in-UI |

**The line for Wednesday:** "I built the loop in Phoenix to prove it works
end-to-end locally with zero infra. It maps 1:1 onto Arize AX for production —
which gives you the managed store your logs need, continuous monitors, alerting,
and team access. Same concepts; migration is lift-and-shift, not a rebuild."

Storage nuance (defensible): both store data. Phoenix already solves "logs
stored nowhere" — instrument the agent and traces persist. What AX adds is
*managed, auto-scaling* storage + the operational layer, NOT storage-vs-none.

## 4. Architecture (text description — the diagram in words)

**Live request path (synchronous):**
```
User → asks Question → routed to → Travel Agent
Travel Agent → CALLS → MCP Tools → RESPONDS_BACK → Travel Agent
   MCP Tools include: search_flight, search_hotels, get_weather, create_itinerary
Travel Agent → RESPONDS_BACK → User   (immediately — user never waits on evals)
```

**Async eval path (out of band — the ASYNC RESPONSE LOOP PATTERN):**
```
Travel Agent response → (non-blocking export) → Raw Log Storage (Bronze)
Bronze → Eval Loop → Silver (cleaned eval results) → Gold (business metrics + cost)
Gold → Dashboard (metrics + cost monitoring) → threshold check → FLAGS → Violations
```
Medallion layering: **Bronze** = raw logged traces; **Silver** = cleaned eval
outputs (post-ETL); **Gold** = aggregated business + quality + cost metrics.

**Eval tooling seam:** Phoenix (local/dev — what we build & demo) and Arize AX
(cloud/prod — design-only mirror) are the SAME loop, swapped per environment.
Both read from the logged-trace store (Bronze), NOT from the live response node.

**Feedback loop closure (design-only):**
```
Violations → LLM-tools generate fix / hot-fix → Draft PRs → Engineering Team (Sophia's)
Engineering Team reviews → merges → UPDATES Travel Agent DIRECTLY
   (loop closes because the improved agent's NEXT responses re-enter the eval loop
    and should score higher — the feedback to the agent is the merged code change,
    not something routed back through the eval tooling)
Threshold violations also → SNS → Engineering Team (alert ASAP)
```

## 5. Eval methodology (the heart of the project)

**Two-stage pipeline inside the eval loop. Deterministic FIRST (a gate), then
LLM-as-judge.**

**Stage 1 — Deterministic rules (free, exact-checkable):**
1. **Validate tool calls** — did the agent actually call the tools (vs fabricate)?
2. **Validate agent response includes real data from the API/tool outputs** —
   do the flights/hotels/prices/weather in the answer match what the tools
   actually returned? (exact-match groundedness — catches fabricated specifics)
3. *(recommended add)* **Validate request params** — destination/dates in the
   itinerary match what the user asked (cheap correctness win).

**Stage 2 — LLM-as-judge (costs tokens; runs on what passes the gate):**
1. **Tone** — professional / brand-appropriate.
2. **Groundedness (faithfulness)** — subtler than Stage-1 exact match: did the
   agent embellish or distort the retrieved data in ways string-matching misses?
3. **Accurate itinerary** — combination of hard-param checks + overall message
   quality/fluency.

**Why deterministic-first matters (SAY THIS — it's the strongest point):** it's
a **cost lever.** Deterministic checks are free; the LLM judge costs tokens on
every call. Gating — only spend judge tokens on responses worth judging —
directly answers the client's #1 concern: "how do we counteract cost as we scale
to millions?"

**Why trust the LLM judge?** A **golden dataset** of human-labeled ground-truth
answers validates the judge (measure agreement, target ~75–90%). The judge USES
the golden set as its foundation. Without this, the judge is asserted, not
trusted.

**Eval type rule:** deterministic when there's an objective checkable truth;
LLM-judge when the judgment is semantic/fuzzy.

## 6. Build vs. Design-only

**BUILD (must work in the demo):**
- Phoenix running locally + sample agent instrumented (traces visible)
- Deterministic checks (tool-call + real-data validation)
- LLM-judge evals (groundedness/faithfulness, tone, itinerary accuracy)
- Small golden dataset + judge validation (agreement %)
- One experiment (old vs. new prompt regression)
- Threshold alerting (metric < X → flag)
- Cost tracking (token/$ per step)

**DESIGN-ONLY (diagram + justify, do NOT build):**
- Continuous/streaming eval at millions/day
- Automated PR generation (LLM-tools hot-fix) + CI wiring
- Production infra (managed store = AX, orchestration, K8s)
- Cost-control-at-scale (sampling, judge-model tiering, batching)
- Availability/uptime + response-latency SLOs
- Team-enablement layer (RBAC, eval guidelines) — AX

## 7. Requirements traceability (coverage check — every stated client need)

| # | Client requirement (from discovery) | How the design covers it | Build / Design |
|---|---|---|---|
| 1 | Phase 1 = itineraries only, no bookings | Scope limited to itinerary evals | Build |
| 2 | Correctness (matches request params) | Stage-1 param check + Stage-2 itinerary-accuracy judge | Build |
| 3 | Groundedness (flights/hotels real & available; RAG) | Stage-1 real-data match + Stage-2 faithfulness judge | Build |
| 4 | Tone (professional) | Stage-2 LLM-judge | Build |
| 5 | Relevance/scope (no token abuse) | Inline scope guardrail | **Design-only** (⚠ not yet placed — see §8) |
| 6 | Human-only eval + golden dataset in spreadsheets | Golden dataset formalized; validates judge | Build (small) |
| 7 | Alert ASAP below threshold (85–95% target) | Threshold monitor → Violations → SNS → Eng team. **We recommend the number** (groundedness likely stricter than correctness) | Build alerting; recommend thresholds |
| 8 | Automated feedback loop: patterns → draft PRs → human review (Sophia's team), NOT auto-merge | Violations → LLM-tools hot-fix → Draft PRs → human merge → direct agent update | Design-only |
| 9 | Cost monitoring at every step | Dashboard cost monitoring + deterministic-first gating | Build tracking; design scale-cost |
| 10 | Timeline 2–3 months to prod | Phasing narrative | Talking point |
| 11 | Scale = COST not throughput (hundreds→millions) | Cost-gating, sampling, judge tiering | Design-only |
| 12 | Modular/reusable framework across many agents | Loop structure is agent-agnostic; only eval defs change per use case | Design principle + talking point |
| 13 | Logs stored nowhere | Medallion (Bronze/Silver/Gold); Phoenix persists traces locally; AX managed store for prod | Build Bronze local; design AX store |
| 14 | Reliability = quality AND availability (emphasis: uptime + response speed) | Async pattern protects latency (eval never in user path); availability = prod infra | Build async; design availability |
| 15 | Evals run continuously | Continuous eval loop (demo runs on-demand/batch) | Design (demo = batch) |
| 16 | Onboard many team members + eval guidelines | AX RBAC/spaces; guidelines deliverable | Design-only |
| 17 | Business metrics: ↑ conversion, ↓ live-support | Gold business metrics; thumbs/conversion signal feeds golden set | Design-only + talking point |

## 8. Open items / talking points (account for these even if not coded)

- **Scope/relevance guardrail (req #5)** — the one secondary eval not yet placed
  on the diagram. Either add an inline "scope check (design-only)" note or state
  explicitly you'd add a cheap inline classifier and left it out of the core loop
  deliberately.
- **Modularity** — say the line: "the loop structure is agent-agnostic; only the
  eval definitions change per use case." (Client's #1 higher-level ask.)
- **Why tracing earns its place** — the deterministic checks only work because
  the trace captures tool inputs/outputs. Connect instrumentation → evals.
- **Availability** — async pattern is *how* you protect the response-speed
  requirement. Name the link.
- **Threshold recommendation** — walk in with a recommended number + reasoning,
  don't just accept 85–90%.

## 9. Tech constraints & first-build checks

- **Repo:** `sample-travel-agent` (already cloned) —
  https://github.com/Arize-ai/sample-travel-agent
- **LLM-as-judge model:** Gemini (Sharan has a Gemini API key). Phoenix supports
  non-OpenAI judge models — wire the judge to Gemini.
- **⚠ FIRST THING TO VERIFY:** what model does the *sample agent itself* require?
  It may be OpenAI-based. If so, either (a) obtain an OpenAI key, or (b) repoint
  the agent to Gemini as well, or (c) mock the agent's LLM calls for the demo.
  Confirm this before anything else — it's the one hard dependency.
- **Instrumentation:** Phoenix `register(auto_instrument=True)` for tracing.
- **Demo runs locally on Sharan's machine** (he presents it live).

## 10. Build sequence (do in this order)

1. **Verify the model dependency** (§9) — get the agent running at all.
2. **Wire Phoenix tracing** — smallest "it works": run the agent, see a trace in
   the Phoenix UI. Nothing else until this works.
3. **Build evals incrementally — groundedness/real-data FIRST** (hardest +
   most impressive), then correctness/params, then tone.
4. **Golden dataset + judge validation** (agreement %).
5. **One experiment** (old vs. new prompt regression).
6. **Threshold alerting + cost tracking.**
7. **Rehearse** the end-to-end walkthrough, timed.

## 11. Working style (for the human, Sharan)

- Pair-programmer / thinking-partner dynamic — Sharan owns understanding and
  decisions; the assistant teaches concepts and pressure-tests, does NOT just
  hand over answers.
- Sharan is new to Phoenix/Arize — **teach the concepts as you build**, don't
  assume familiarity.
- Sharan tends to under-rate his own work and reach for more complexity than
  needed. Push back on both: the design is done; the win now is *working code*,
  not more depth.
