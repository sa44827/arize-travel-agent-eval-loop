"""One eval cycle: fetch new turns -> Stage 1 gate -> Stage 2 judges -> annotate -> Gold summary.

    python -m evals.run_evals [--project NAME]

Idempotent: only turns without the GATE annotation are processed, so the scheduler
(evals/scheduler.py) can call this on a loop. Bronze = Phoenix traces, Silver = the
annotations written here, Gold = the summary + threshold check at the end.
"""

import argparse
import json
import logging

import pandas as pd
from phoenix.client import Client

from evals.deterministic import gate_passed, run_checks
from evals.judges import run_judges
from evals.thresholds import check_thresholds
from evals.turns import GATE, PROJECT, fetch_turns

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _row(span_id: str, name: str, res: dict, kind: str) -> dict:
    return {"context.span_id": span_id, "name": name, "annotator_kind": kind,
            "label": res["label"], "score": float(res["score"]), "explanation": res["explanation"][:1000]}


def _judge_cost(client: Client, project: str) -> dict:
    """All-time judge token spend from the sibling '<project>-evals' project
    (see agent/tracing.py init_tracing / evals/judges.py). Reported separately
    from agent cost per the client's explicit ask for both numbers."""
    try:
        df = client.spans.get_spans_dataframe(project_identifier=f"{project}-evals", limit=5000)
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}
    if df is None or df.empty:
        return {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}
    cols = {
        "prompt_tokens": "attributes.llm.token_count.prompt",
        "completion_tokens": "attributes.llm.token_count.completion",
        "reasoning_tokens": "attributes.llm.token_count.completion_details.reasoning",
    }
    return {k: int(df[c].fillna(0).sum()) if c in df else 0 for k, c in cols.items()}


def run_cycle(project: str = PROJECT, rescore: bool = False) -> dict:
    client = Client()
    turns = fetch_turns(project, only_unscored=not rescore)
    if turns.empty:
        log.info("No unscored turns.")
        return {"turns": 0}

    rows, passed = [], []
    for _, t in turns.iterrows():
        checks = run_checks(t.to_dict())
        rows += [_row(t["span_id"], n, r, "CODE") for n, r in checks.items()]
        if gate_passed(checks):
            passed.append(t)
        else:
            failed = [n for n, r in checks.items() if r["label"] == "fail"]
            rows.append(_row(t["span_id"], GATE, {"label": "fail", "score": 0, "explanation": f"failed: {failed}"}, "CODE"))
            log.info("GATE FAIL %s %s", t["span_id"][:8], {n: checks[n]["explanation"][:90] for n in failed})

    judged = run_judges(pd.DataFrame(passed)) if passed else {}
    complete = 0
    for sid, verdicts in judged.items():
        rows += [_row(sid, n, v, "LLM") for n, v in verdicts.items()]
        if {"groundedness", "tone"} <= verdicts.keys():  # else leave unscored -> retried next cycle
            complete += 1
            rows.append(_row(sid, GATE, {"label": "pass", "score": 1, "explanation": "judged"}, "CODE"))

    if rows:
        client.spans.log_span_annotations_dataframe(dataframe=pd.DataFrame(rows))

    # Gold: pass rates over ALL scored turns in the project, not just this cycle
    spans = client.spans.get_spans_dataframe(project_identifier=project, limit=5000)
    if "context.span_id" not in spans:
        spans = spans.reset_index()
    agent = spans[spans["span_kind"] == "AGENT"].set_index("context.span_id", drop=False)
    ann = client.spans.get_span_annotations_dataframe(spans_dataframe=agent, project_identifier=project)
    violations = check_thresholds(ann) if ann is not None and len(ann) else []

    gate_fail = len(turns) - len(passed)
    summary = {
        "new_turns": len(turns),
        "fallback_turns": int(turns["fallback"].sum()),
        "gate_failed": gate_fail,
        "judged": complete,
        "judge_calls_saved": gate_fail * 2,  # >= 2 judges skipped per gated-out turn
        "agent_tokens_this_cycle": {k: int(turns[k].sum()) for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens")},
        "judge_tokens_all_time": _judge_cost(client, project),  # separate line item, per client requirement
        "violations": violations,
    }
    log.info("Summary: %s", json.dumps(summary))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--rescore", action="store_true", help="re-evaluate already-scored turns (after changing checks/judges)")
    args = ap.parse_args()
    print(json.dumps(run_cycle(args.project, args.rescore), indent=2))
