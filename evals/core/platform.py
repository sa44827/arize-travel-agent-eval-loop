"""Register the LLM judges with Phoenix as first-class dataset evaluators.

Phoenix 20.4 keeps a server-side evaluator registry (the Evaluators page). It is
GraphQL-only, which is easy to miss if you go looking in the REST spec. Judges
registered here are stored and executed *by Phoenix*, attached to a dataset, and
usable from the Playground without touching this repo.

Only the LLM judges are registered. They are a prompt plus a choice mapping,
which is exactly what the platform stores. The Tier-1 code evaluators import
`truth.py` and read the JSON fixtures off disk, so putting them in a Phoenix
sandbox would mean duplicating ground truth into a second place — and duplicated
ground truth is how before/after comparisons quietly stop being comparable. They
stay in-repo, where the pytest CI gate needs them anyway.

    python -m evals.core.platform --list
    python -m evals.core.platform --register
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parents[2]
BASE = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006").rstrip("/")

CREATE = """
mutation Create($input: CreateDatasetLLMEvaluatorInput!) {
  createDatasetLlmEvaluator(input: $input) {
    evaluator { id name }
  }
}
"""

LIST = """
{ evaluators { edges { node { id name kind } } } }
"""


def gql(query: str, variables: dict | None = None) -> Any:
    req = urllib.request.Request(
        f"{BASE}/graphql",
        method="POST",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], indent=2)[:1200])
    return body["data"]


def dataset_id(name: str) -> str:
    from phoenix.client import Client

    return Client().datasets.get_dataset(dataset=name).id


def register(dataset: str, *, model: str = "claude-haiku-4-5") -> list[str]:
    """Create one Phoenix evaluator per custom judge."""
    from evals.agents.travel import judges as J

    ds = dataset_id(dataset)

    # Only the custom classifiers: the pre-builts (hallucination,
    # tool_response_handling) already exist as Phoenix built-ins, so
    # re-uploading their prompts would fork them from the library version.
    specs = [
        {
            "name": "graceful_alternative",
            "template": J.GRACEFUL_TEMPLATE,
            "labels": [("graceful", 1.0), ("unhelpful", 0.0)],
            "direction": "MAXIMIZE",
            "paths": {"request": "input.message", "reply": "output.reply"},
            "description": "No-result and out-of-scope replies state the outcome "
                           "and name a real next step.",
        },
        {
            "name": "recommendation_grounded",
            "template": J.RECOMMENDATION_TEMPLATE,
            "labels": [("grounded", 1.0), ("ungrounded", 0.0)],
            "direction": "MAXIMIZE",
            "paths": {
                "request": "input.message",
                "results": "output.tool_calls",
                "reply": "output.reply",
            },
            "description": "Every claim is about a field the tool results "
                           "actually contain; superlatives are true of that set.",
        },
    ]

    created = []
    for spec in specs:
        payload = {
            "datasetId": ds,
            "name": spec["name"],
            "description": spec["description"],
            "promptVersion": {
                "modelProvider": "ANTHROPIC",
                "modelName": model,
                "templateFormat": "MUSTACHE",
                "template": {
                    "messages": [
                        {
                            "role": "USER",
                            "content": [{"text": {"text": spec["template"]}}],
                        }
                    ]
                },
                # OneOf input: exactly one provider key, matching modelProvider.
                "invocationParameters": {"anthropic": {"maxTokens": 1024}},
                # Phoenix requires evaluator prompts to emit their verdict as a
                # forced tool call rather than free text — the same structured
                # output `ClassificationEvaluator` gets client-side, declared
                # explicitly here. The enum must match the outputConfigs labels
                # or the score has nothing to map onto.
                "tools": {
                    "tools": [
                        {
                            "function": {
                                # Phoenix matches the tool to its output config
                                # by name, so these must be identical.
                                "name": spec["name"],
                                "description": spec["description"],
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "explanation": {
                                            "type": "string",
                                            "description": "Why this label, citing the evidence.",
                                        },
                                        "label": {
                                            "type": "string",
                                            # Phoenix ties the annotation to the
                                            # schema through this field: the
                                            # label property's description must
                                            # equal the output config's name.
                                            "description": spec["name"],
                                            "enum": [lbl for lbl, _ in spec["labels"]],
                                        },
                                    },
                                    "required": ["explanation", "label"],
                                },
                            }
                        }
                    ],
                    "toolChoice": {"functionName": spec["name"]},
                    "disableParallelToolCalls": True,
                },
            },
            "outputConfigs": [
                {
                    "categorical": {
                        "name": spec["name"],
                        "description": spec["description"],
                        "optimizationDirection": spec["direction"],
                        "values": [
                            {"label": label, "score": score}
                            for label, score in spec["labels"]
                        ],
                    }
                }
            ],
            "inputMapping": {
                "literalMapping": {},
                "pathMapping": spec["paths"],
            },
        }
        data = gql(CREATE, {"input": payload})
        created.append(data["createDatasetLlmEvaluator"]["evaluator"]["name"])
    return created


def listing() -> list[dict]:
    data = gql(LIST)
    return [e["node"] for e in data["evaluators"]["edges"]]


def main() -> None:
    sys.path.insert(0, str(HERE))
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dataset", default="travel-golden-v1")
    args = ap.parse_args()

    if args.register:
        made = register(args.dataset)
        print(f"registered {len(made)}: {', '.join(made)}")
    if args.list or not args.register:
        rows = listing()
        print(f"{len(rows)} evaluator(s) in Phoenix:")
        for r in rows:
            print(f"  {r['name']:26} {r['kind']:6} {r['id']}")


if __name__ == "__main__":
    main()
