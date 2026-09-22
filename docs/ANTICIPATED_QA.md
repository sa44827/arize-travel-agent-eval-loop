# Anticipated Q&A — Interview 2

Organized against the PDF's own "What We Are Evaluating" list (evaluation methodology,
production readiness, systems thinking, tradeoff discussions, technical judgment,
handling ambiguity). Every answer is grounded in something we actually built or found
— cite `docs/BUILD_LOG.md` entry numbers when it strengthens the answer. Harder,
skeptical questions are included deliberately — those are the ones that actually get
asked to someone senior.

---

## Architecture & design decisions

**Q: Why Phoenix and not Arize AX directly, if AX is the production recommendation?**
Phoenix proves the loop works end-to-end with zero infra, locally, for free. Same
tracing (OTel/OpenInference), same eval SDK — moving to AX is a config change to where
traces are sent, not a rebuild. Building against AX directly would mean the interviewer
can't see the mechanism run live without a hosted account and cost — Phoenix removes
that friction for the demo without changing the engineering story.

**Q: Your diagram shows separate Silver and Gold storage. You built neither. Why?**
Silver is Phoenix's own span-annotation store — we write eval results there as
structured annotations tied to the span they graded, which is exactly what "cleaned
eval output" means. Gold is a query over those annotations (pass rates, thresholds),
computed on demand, not persisted separately. Standing up two more databases to match
a diagram, when Phoenix already serves the read pattern, would be storage for its own
sake. The honest boundary: today Gold is a query; at real production volume, AX's
managed store and continuous monitors are exactly the layer that turns that into an
incrementally-updated rollup instead of a recompute. Same logical layer, different
execution at different scale. (`docs/BUILD_LOG.md` #35)

**Q: The diagram says "MCP Tools." Are these MCP tools?**
No — plain Python functions with a JSON schema, called directly by the model's native
tool-calling. Worth saying plainly if asked rather than let the diagram's label stand
uncorrected: MCP would be the right choice if these tools needed to be shared across
multiple agents or processes; for one agent with four in-process functions, it's
unnecessary indirection. If the framework needs to support many future agents sharing
a tool registry (the client's stated modularity goal), that's exactly when MCP earns
its place — that's a legitimate "what changes at the next stage" answer.

**Q: Why Gemini and not the Anthropic SDK the sample repo shipped with?**
No Anthropic key available; Gemini's free tier let us build and iterate without a
budget ask. The port was mechanical — same tool-calling loop shape, same JSON schema
format reused directly (`parameters_json_schema` accepted the Anthropic-style
`input_schema` unmodified). Worth being honest that this introduced today's real
constraint: free-tier daily quotas, which became part of the production-readiness
story rather than an unrelated inconvenience.

---

## Evaluation methodology

**Q: Why two stages instead of just an LLM judge for everything?**
Cost, directly. The client's own words: *"less the scale of users, more so scale of
cost... how can we counteract that?"* A deterministic check is free and exact where
exactness is possible (does this flight number exist in the tool's output?). Running
an LLM judge on every response regardless would mean judge cost scales linearly with
traffic with no lever to pull. In one real run, the gate skipped 17 of 23 judge calls
— that's not a hypothetical saving, it's a measured one.

**Q: How do you know the deterministic checks aren't just wrong in a different way —
i.e., false negatives you're not seeing?**
Two things: every check fails closed (unable to verify → fail, never a silent pass),
and we validated them against traffic we knew contained specific seeded defects
(reversed flight direction, an off-by-one itinerary bug) — the checks caught those on
the first real run, which is direct evidence they discriminate rather than rubber-stamp.
We also found and fixed a case where a check *did* fail open early in the build
(`docs/BUILD_LOG.md` #18) — a 100% pass rate on traffic we knew was broken was the
signal that caught it. That's the standing rule now: a suspiciously clean number is a
prompt to go look, not a result to report.

**Q: Why trust an LLM to judge another LLM?**
We don't, by default — we measured it. Round 1 (blind human labels) came back at 47%
agreement with the judge, kappa −0.03 — statistically no better than chance. Rather
than accept that or quietly retune until the number looked better, we found *why*: the
judge and the human were drawing the line on "embellishment" differently. We calibrated
the rubric with the domain owner, then re-measured: 89% agreement, kappa 0.79. Two
remaining disagreements were left alone rather than tuned away, and that process — not
the final number — is the actual answer to "why trust it."

**Q: What if the judge is systematically lenient/strict in a way your golden set of 19
turns doesn't reveal?**
Real risk, and honestly named as a limitation: 19 turns is enough to calibrate a
rubric, not to certify a population estimate. The design answer is periodic
re-sampling against fresh human labels as traffic grows — not a one-time validation
treated as permanent. We'd also watch the judge's pass-rate distribution in
production: a judge that never fails anything, or fails everything, is a signal to
re-calibrate regardless of the original agreement number.

**Q: Why these specific thresholds (90-95%) and not the 85-95% the client suggested?**
We recommended per-eval numbers rather than one blanket target, and said why: exact
checks (tool_contract, reply_grounded) get the strictest bar (95%) because they're
checkable with certainty — a failure there is unambiguous. The LLM judge gets a
slightly lower bar (90%) because it carries irreducible judge noise even after
calibration. Itinerary accuracy is lowest (85%) because it has the fewest samples.
Walking in with a reasoned number, not just accepting theirs, was itself something the
client explicitly invited (transcript: *"would obviously love your suggestions... give
us your recommendations"*).

---

## Production readiness & scale

**Q: What actually breaks first at a million requests/day?**
Not throughput — the client said as much themselves (*"less the scale of users, more
so scale of cost"*). Judge cost breaks first: every gate-passing turn costs an LLM
call. The levers, in order: the deterministic gate (already built, already measured),
then sampling (evaluate every Nth turn, not every turn), then judge-model tiering
(cheap model for routine checks, expensive model only when the cheap one is uncertain
or on a random audit sample). None of the latter two are built — they're one-line
design commitments we'd size against real traffic data, not guessed numbers.

**Q: What's your actual rollback story?**
Git. Every fix is one commit citing the violation that caused it — `git revert` undoes
exactly that change with a clear paper trail. The prompt specifically: v1 is kept
byte-for-byte alongside v2, selected by an env var (`PROMPT_VERSION`) — a rollback is a
config flip, not a code change or a redeploy of old logic.

**Q: How do you handle a partial outage — say, the judge model going down mid-run?**
We hit this for real, not hypothetically: the judge's daily quota fully exhausted
mid-scheduler-run and crashed the eval cycle. Two things were true and one needed
fixing: Stage 1 (free, deterministic) had already computed its results in memory when
the crash happened, and the original code would have discarded those too rather than
just losing the paid Stage 2 work. Fixed so a total Stage-2 outage never blocks Stage
1 from being written — degraded, not down. (`docs/BUILD_LOG.md` #37)

**Q: Secrets management?**
`.env`, gitignored, for this build. Named explicitly as the wrong answer at real scale
— a secrets manager (AWS Secrets Manager, GCP Secret Manager, Vault) is what AX
deployment would actually use; `.env` files are a local-dev convenience, not a
production security posture, and I wouldn't defend it as one if pushed.

**Q: What's the latency/availability story — how does the eval loop not slow down the
user?**
Structurally, not just by intent: the agent responds synchronously to the user before
any eval runs. The eval loop reads from Bronze (the already-persisted trace) out of
band — there's no code path where a user's response waits on an eval. This is a direct
answer to the client's own words: *"nothing's worse than talking with a chatbot and
waiting five minutes for a response."*

**Q: Free-tier Gemini — is that a security or reliability concern for a real
customer?**
Two separate concerns, both real. Reliability: free-tier daily quotas are a hard cap
we hit ourselves during this build (`docs/BUILD_LOG.md` #31, #37) — a production
deployment needs a paid tier with headroom, not a free key. Security/data: free-tier
traffic can be used by the provider for model improvement depending on terms — a real
customer needs a paid tier or a zero-retention agreement (e.g. Vertex AI), not the
default consumer terms. Both are one-line fixes (a billing account, a tier flag), not
architectural changes.

---

## Results, tradeoffs & "what would you do differently"

**Q: Walk me through a bug the loop actually caught, end to end.**
`search_flights` matched cities as an unordered set — a request for NY→Miami also
returned Miami→NY flights. The `tool_contract` check flagged it directly:
"AA 2210 flies Miami→New York, requested New York→Miami." Fixed in one commit citing
that exact finding, re-ran the same baseline traffic, `tool_contract` went from 35% to
100%. That's the shape of every fix in this build — eval finding → cited commit →
re-measured, not "we changed some things and it feels better."

**Q: You introduced your own bug while fixing things. Isn't that a problem?**
It's the strongest evidence in the whole build, not a weakness to downplay. The v2
prompt's honesty instruction leaked "this is a demo system with fake data" to users —
exactly the internal-systems leak another line in the same prompt was supposed to
prevent. The eval loop caught it the same day, on our own change, with no special
handling — which is the actual test of whether a feedback loop works: does it catch
regressions from the team building it, not just the seeded defects it was tuned to find.

**Q: What would you build next if given another two weeks?**
In priority order: (1) the retry-cap fix for partial-quota conditions — a known,
diagnosed, unfixed gap; (2) the scope-guardrail classifier (relevance/on-topic), the
one secondary requirement from discovery not yet placed anywhere in the loop; (3) a
second, larger controlled experiment now that the tool bugs are fixed, to see if
further prompt iteration keeps moving groundedness up without a tone regression;
(4) real judge-cost tiering, sized against whatever traffic volume shows up first.

**Q: What was actually hard about this, technically?**
Getting evaluable structure into the traces. Auto-instrumentation traces the SDK calls,
not the agent's logic — the first pass had one flat LLM span per model call with no
way to see which tool ran, what it returned, or which turn a fallback happened on.
Had to add explicit `agent_turn` and `tool` spans by hand before any of the
deterministic checks could be exact rather than regex-guessing at a raw SDK response
blob.

**Q: If this whole thing had to run for a real customer starting Monday, what's the
biggest thing you're NOT confident in?**
The judge's calibration holding up outside the 19-turn set it was tuned on, and the
partial-quota retry behavior under real production rate limits (not free-tier ones,
but the same *class* of failure — a degraded dependency). Both are named, not hidden,
in `docs/BUILD_LOG.md`, and both have a stated next step rather than a hand-wave.

---

## Curveballs

**Q: Why not just use a bigger/better agent model and skip most of the evals?**
That doesn't address groundedness or correctness structurally — a better model still
has no way to *prove* its flight numbers are real without something checking them
against the source of truth, and the client's core failure modes (correctness,
groundedness) are exactly the class of error a bigger model reduces the *rate* of but
doesn't eliminate. The eval loop is the only piece that turns "probably better" into
"measured and monitored."

**Q: Isn't a deterministic check on hard-coded fixture data cheating — this won't work
against a real live booking API?**
The check's *shape* generalizes even though the fixture is a stand-in: compare the
reply's claims against whatever the tool actually returned for that call. Against a
real API, the tool's response is still the ground truth for that turn — the check
logic doesn't change, only the data source underneath the tool does.

**Q: How is this eval loop "modular across other agents," concretely, not just as a
claim?**
The loop's shape (trace → deterministic gate → judge on gate-passers → annotate →
threshold-check) has zero travel-specific logic in it. What's travel-specific lives
entirely in `evals/deterministic.py`'s three check functions and `evals/judges.py`'s
three prompt templates — swap those for a different domain's checks and judges, and
`run_evals.py`, `scheduler.py`, `thresholds.py`, and the tracing wiring are unchanged.

**Q: What don't you know that you wish you did before walking in here?**
Whether the judge-calibration numbers hold on a genuinely fresh (not-yet-seen) sample
— we only ever validated against the 19 turns used to build the rubric. That's a
real, stated gap, not a rhetorical one.
