"""Agent-agnostic experiment runner.

Turns a golden dataset into a Phoenix experiment. Knows nothing about travel —
the agent under test is injected as a callable, and its evaluators come from
the registry by name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from phoenix.client import Client
from phoenix.client.experiments import run_experiment

from evals.core.registry import REGISTRY, RegisteredEvaluator


def load_golden(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text())


def upload_dataset(name: str, examples: list[dict], *, client: Client | None = None):
    """Upsert the golden set into Phoenix.

    Stable `id`s mean re-uploading updates rows in place rather than appending
    duplicates, so the dataset keeps one identity across regenerations.
    """
    client = client or Client()
    return client.datasets.create_dataset(
        name=name,
        examples=[
            {
                "id": e["id"],
                "input": e["input"],
                "output": e["output"],
                "metadata": e["metadata"],
            }
            for e in examples
        ],
    )


# --------------------------------------------------------------------------
# Turning one agent turn into an evaluable record
# --------------------------------------------------------------------------

def extract_tool_calls(messages: list) -> list[dict]:
    """Recover (name, input, output) triples from an Anthropic message history.

    Reading the transcript rather than instrumenting the agent keeps the agent
    untouched — the brief is explicit that agent changes should come out of the
    eval loop, not out of building it.
    """
    pending: dict[str, dict] = {}
    calls: list[dict] = []

    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            btype = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )
            if btype == "tool_use":
                bid = getattr(block, "id", None) or block.get("id")
                rec = {
                    "name": getattr(block, "name", None) or block.get("name"),
                    "input": getattr(block, "input", None) or block.get("input"),
                    "output": None,
                }
                pending[bid] = rec
                calls.append(rec)
            elif btype == "tool_result":
                bid = (
                    getattr(block, "tool_use_id", None)
                    if not isinstance(block, dict)
                    else block.get("tool_use_id")
                )
                raw = (
                    getattr(block, "content", None)
                    if not isinstance(block, dict)
                    else block.get("content")
                )
                if bid in pending:
                    try:
                        pending[bid]["output"] = json.loads(raw)
                    except (TypeError, ValueError):
                        pending[bid]["output"] = raw
    return calls


def make_task(agent_fn: Callable[[list], tuple[str, list]]) -> Callable[[dict], dict]:
    """Wrap an agent turn function into a Phoenix experiment task."""

    def task(input: dict) -> dict:
        messages = [{"role": "user", "content": input["message"]}]
        reply, history = agent_fn(messages)
        return {"reply": reply, "tool_calls": extract_tool_calls(history)}

    return task


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def evaluators_for(
    agent: str,
    *,
    mode: str | None = None,
    kind: str | None = None,
    names: list[str] | None = None,
):
    regs: list[RegisteredEvaluator] = REGISTRY.for_agent(agent, mode=mode, kind=kind)
    if names:
        # Selecting judges by name keeps an experiment's cost proportional to the
        # question being asked — running all four on every example doubles the
        # bill to corroborate a result two of them already settle.
        wanted = set(names)
        regs = [r for r in REGISTRY.for_agent(agent) if r.name in wanted]
    return [r.evaluator for r in regs]


def run(
    *,
    agent: str,
    dataset_name: str,
    agent_fn: Callable[[list], tuple[str, list]],
    experiment_name: str,
    kind: str | None = "code",
    names: list[str] | None = None,
    dry_run: int | bool = False,
    repetitions: int = 1,
    client: Client | None = None,
):
    client = client or Client()
    dataset = client.datasets.get_dataset(dataset=dataset_name)
    return run_experiment(
        dataset=dataset,
        task=make_task(agent_fn),
        evaluators=evaluators_for(agent, kind=kind, names=names),
        experiment_name=experiment_name,
        dry_run=dry_run,
        repetitions=repetitions,
    )
