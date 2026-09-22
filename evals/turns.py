"""Load agent turns (one trace = one user turn) from Phoenix.

Bronze -> eval input. Each row has the user input, final reply, fallback flag,
every tool call (args + result, from TOOL spans) and token usage (from LLM spans).
Idempotency: a turn is "scored" once it carries the GATE annotation. No state file.
"""

import json
import os

import pandas as pd
from phoenix.client import Client

PROJECT = os.getenv("PHOENIX_PROJECT", "travel-agent")
GATE = "gate"  # written last for every turn; presence = scored


def _json(v):
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


def _tok(df: pd.DataFrame, col: str) -> int:
    return int(df[col].fillna(0).sum()) if col in df else 0


def fetch_turns(project: str = PROJECT, only_unscored: bool = True, limit: int = 5000) -> pd.DataFrame:
    client = Client()
    spans = client.spans.get_spans_dataframe(project_identifier=project, limit=limit)
    if spans is None or spans.empty or "span_kind" not in spans:
        return pd.DataFrame()
    if "context.span_id" not in spans:
        spans = spans.reset_index()

    turns = spans[spans["span_kind"] == "AGENT"].sort_values("start_time")

    tools = spans[spans["span_kind"] == "TOOL"].sort_values("start_time").groupby("context.trace_id")
    llms = spans[spans["span_kind"] == "LLM"].groupby("context.trace_id")

    rows = []
    for _, t in turns.iterrows():
        tid = t["context.trace_id"]
        calls = []
        if tid in tools.groups:
            for _, s in tools.get_group(tid).iterrows():
                calls.append({
                    "name": s["name"],
                    "args": _json(s.get("attributes.input.value")),
                    "result": _json(s.get("attributes.output.value")),
                })
        llm = llms.get_group(tid) if tid in llms.groups else pd.DataFrame()
        agent_attrs = t.get("attributes.agent")
        rows.append({
            "span_id": t["context.span_id"],
            "trace_id": tid,
            "session_id": t.get("attributes.session.id"),
            "context_calls": [],  # tool calls from earlier turns of the same session (filled below)
            "input": str(t.get("attributes.input.value") or ""),
            "output": str(t.get("attributes.output.value") or ""),
            "fallback": bool(agent_attrs.get("fallback")) if isinstance(agent_attrs, dict) else False,
            "tool_calls": calls,
            "llm_calls": len(llm),
            "prompt_tokens": _tok(llm, "attributes.llm.token_count.prompt"),
            "completion_tokens": _tok(llm, "attributes.llm.token_count.completion"),
            "reasoning_tokens": _tok(llm, "attributes.llm.token_count.completion_details.reasoning"),
        })
    seen: dict = {}
    for r in rows:  # follow-up turns may legitimately reuse results fetched in earlier turns
        r["context_calls"] = list(seen.get(r["session_id"], []))
        seen.setdefault(r["session_id"], []).extend(r["tool_calls"])
    out = pd.DataFrame(rows)
    if only_unscored and not out.empty:
        ann = client.spans.get_span_annotations_dataframe(
            spans_dataframe=turns.set_index("context.span_id", drop=False), project_identifier=project
        )
        if ann is not None and len(ann):
            out = out[~out["span_id"].isin(set(ann.index[ann["annotation_name"] == GATE]))].reset_index(drop=True)
    return out
