"""Upload judge-validation sets as Phoenix datasets for meta-evaluation.

Two different experiments run against two different kinds of dataset, and
keeping them straight is the whole trick:

  travel-golden-v1     task = the agent        evaluators = the judges
                       "is the agent right?"   Python only — the task is a
                                               tool-calling loop, not a prompt.

  judge-validation-*   task = the JUDGE prompt evaluator = exact_match vs label
                       "is the judge right?"   Runs in the Playground, because
                                               here the task really is a prompt.

**One dataset per judge.** An earlier version put both judges' cases in one
dataset and relied on filtering in the UI. The default view is "All Examples",
so the headline read 78% — the grounding judge scoring 100/100 on its own rows
and 0/28 on rows written for a different rubric. A number that is only correct
if you remember to filter is a number that will be misread. Separate datasets
make that mistake impossible rather than merely avoidable.

Inputs are flattened to exactly the judge templates' mustache variables, because
the Playground resolves task-prompt variables from the example's *input* alone.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]
SRC = HERE / "evals" / "data" / "judge_validation_v1.json"

#: name -> (labels it covers, dataset name)
SUITES = {
    "recommendation_grounded": ({"grounded", "ungrounded"}, "judge-validation-grounding-v1"),
    "graceful_alternative": ({"graceful", "unhelpful"}, "judge-validation-graceful-v1"),
}

EXACT_MATCH_ID = "QnVpbHRJbkV2YWx1YXRvcjoy"

#: The judge emits its verdict as a forced tool call, so the label is nested in
#: the assistant message rather than sitting at the top of the task output.
ACTUAL_PATH = "output.messages[0].tool_calls[0].function.arguments.label"


def examples_for(judge: str) -> list[dict]:
    labels, _ = SUITES[judge]
    rows = [r for r in json.loads(SRC.read_text()) if r["label"] in labels]
    out = []
    for r in rows:
        payload = r["output"]
        calls = payload.get("tool_calls") or []
        # Mustache substitutes strings, so tool results arrive pre-serialised —
        # the same JSON the client-side judge is handed.
        results = json.dumps(calls[0].get("output"), sort_keys=True) if calls else "[]"
        out.append({
            "id": r["id"],
            "input": {
                "request": r["input"]["message"],
                "results": results,
                "reply": payload.get("reply", ""),
            },
            "output": {"label": r["label"]},
            "metadata": {"corruption": r["corruption"], "judge": judge},
        })
    return out


def attach_exact_match(dataset_id: str, judge: str) -> str:
    from evals.core.platform import gql

    mutation = """
    mutation($input: CreateDatasetBuiltinEvaluatorInput!) {
      createDatasetBuiltinEvaluator(input: $input) { evaluator { id name } }
    }
    """
    name = f"{judge}_agrees_with_label"
    payload = {
        "datasetId": dataset_id,
        "evaluatorId": EXACT_MATCH_ID,
        "name": name,
        "description": f"Does {judge}'s verdict match the ground-truth label?",
        "inputMapping": {
            "literalMapping": {"case_sensitive": False},
            "pathMapping": {"expected": "reference.label", "actual": ACTUAL_PATH},
        },
        "outputConfigs": [{
            "categorical": {
                "name": name,
                "description": "Judge verdict vs ground truth",
                "optimizationDirection": "MAXIMIZE",
                "values": [
                    {"label": "match", "score": 1.0},
                    {"label": "mismatch", "score": 0.0},
                ],
            }
        }],
    }
    data = gql(mutation, {"input": payload})
    return data["createDatasetBuiltinEvaluator"]["evaluator"]["name"]


def main() -> None:
    sys.path.insert(0, str(HERE))
    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    from phoenix.client import Client

    client = Client()
    for judge, (_, ds_name) in SUITES.items():
        examples = examples_for(judge)
        ds = client.datasets.create_dataset(name=ds_name, examples=examples)
        labels = Counter(e["output"]["label"] for e in examples)
        print(f"{ds_name}  ({ds.id})")
        print(f"  {len(examples)} examples, labels={dict(labels)}")
        try:
            attached = attach_exact_match(ds.id, judge)
            print(f"  evaluator attached: {attached}")
        except (RuntimeError, urllib.error.URLError) as exc:
            # RuntimeError is a GraphQL-level rejection (e.g. already attached);
            # URLError is Phoenix being unreachable. Anything else is a bug here
            # and should surface rather than be printed and stepped over.
            print(f"  evaluator NOT attached: {str(exc)[:200]}")
        print()


if __name__ == "__main__":
    main()
