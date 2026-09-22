"""Gold layer: pass-rate per eval from Phoenix annotations, flagged against thresholds.

Why these numbers (client asked 85-95%; we recommend per-eval, not one blanket target):
  reply_grounded / tool_contract 0.95  exact-checkable, fabricated or wrong specifics harm users -> strictest
  groundedness (judge)           0.90  semantic backstop; some judge noise tolerated
  tool_called                    0.90  most in-scope requests must use a tool
  tone                           0.90  easy to get right; brand risk
  itinerary_accuracy             0.85  fuzzier, fewer samples
Violations are logged and annotated; production would also page (SNS -> on-call), design-only here.
"""

import logging

log = logging.getLogger(__name__)

THRESHOLDS = {
    "tool_called": 0.90,
    "reply_grounded": 0.95,
    "tool_contract": 0.95,
    "groundedness": 0.90,
    "tone": 0.90,
    "itinerary_accuracy": 0.85,
}


def pass_rates(ann) -> dict[str, tuple[float, int]]:
    """{eval: (pass_rate, n)} ignoring 'skip' results."""
    scored = ann[(ann["annotation_name"].isin(THRESHOLDS)) & (ann["result.label"] != "skip")]
    grouped = scored.groupby("annotation_name")["result.score"].agg(["mean", "count"])
    return {name: (float(r["mean"]), int(r["count"])) for name, r in grouped.iterrows()}


def check_thresholds(ann) -> list[dict]:
    violations = []
    for name, (rate, n) in pass_rates(ann).items():
        limit = THRESHOLDS[name]
        ok = rate >= limit
        (log.info if ok else log.warning)("%s %s pass_rate=%.0f%% threshold=%.0f%% n=%d",
                                           "OK       " if ok else "VIOLATION", name, rate * 100, limit * 100, n)
        if not ok:
            violations.append({"eval": name, "pass_rate": round(rate, 3), "threshold": limit, "n": n})
    return violations
