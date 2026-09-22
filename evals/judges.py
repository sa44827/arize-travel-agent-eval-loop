"""Stage 2 — LLM-as-judge (Gemini via phoenix-evals). Runs only on turns that passed Stage 1.

  groundedness        reply vs the tool results for THIS turn (the reference) — nuance beyond exact match
  tone                professional / brand-appropriate for a public travel agent
  itinerary_accuracy  itinerary turns only: right destination, length, plausible structure

No cache and no state: idempotency comes from the GATE annotation (see turns.py),
so a failed judge call simply leaves the turn unscored and it is retried next cycle.
"""

import json
import os
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from phoenix.evals import LLM, ClassificationEvaluator, evaluate_dataframe

from agent.config import JUDGE_MODEL
from evals.deterministic import is_itinerary

load_dotenv()
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):  # phoenix-evals reads GOOGLE_API_KEY
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# The fixture data spans dates that straddle "now" (some 2026 dates are already
# past by the time this runs). Without today's date the judge can't tell past
# from future and flags correct past-tense replies as hallucinated — same fix
# as agent/prompt.py's {today}. TODAY_DATE is a plain-text token (not `{today}`)
# so it can't collide with the {{...}} placeholders phoenix-evals fills in.
TODAY_DATE = date.today().strftime("%A, %B %d, %Y")

GROUNDEDNESS = """You are auditing a travel agent's reply against the tool results it received.
Today's date is TODAY_DATE.

<user_request>{{input}}</user_request>
<tool_results>{{reference}}</tool_results>
<agent_reply>{{output}}</agent_reply>

The tool results are the ONLY source of truth for HARD FACTS: hotel and airline names, flight numbers,
prices, ratings, times and dates, availability, route attributes (nonstop/direct, airports or airport codes,
next-day arrival) and weather values. Tool results of [] mean nothing was found. Ignore whether dates seem
far in the future.

ungrounded - the reply contains a hard fact the tool results do not support (including one that is
             distorted or invented), presents invented options as real, claims a capability the agent
             has no tool for (e.g. processing refunds, booking, cancelling), or states authoritative
             general facts (visa, legal, policy) that no tool supports
grounded   - every hard fact matches the tool results, or the reply honestly says nothing was found.
             Subjective color that makes no hard-fact claim (great views, nice vibe, a lovely option,
             neighborhood feel) and pleasantries are fine and must NOT be penalized

Answer with one word: grounded or ungrounded."""

TONE = """You are reviewing the tone of a public-facing travel company's agent.
Today's date is TODAY_DATE.

<user_request>{{input}}</user_request>
<agent_reply>{{output}}</agent_reply>

professional   - courteous, clear, concrete, brand-appropriate; does not expose internal systems.
                 Honestly saying nothing was found, and suggesting different dates or a nearby city,
                 is professional and NOT dismissive -- that is the correct behavior for an empty result.
unprofessional - rude, sloppy, overly casual, evasive, exposes internals, sends the user to another
                 website, or is factually confused about dates given today's date above

Answer with one word: professional or unprofessional."""

ITINERARY = """You are checking a trip itinerary produced by a travel agent.

<user_request>{{input}}</user_request>
<tool_results>{{reference}}</tool_results>
<agent_reply>{{output}}</agent_reply>

accurate   - right destination, the number of days the user asked for, and a sensible day-by-day plan consistent with the tool results
inaccurate - wrong destination, wrong number of days, or contradicts the request or tool results

Answer with one word: accurate or inaccurate."""

JUDGES = {
    "groundedness": (GROUNDEDNESS.replace("TODAY_DATE", TODAY_DATE), {"grounded": 1, "ungrounded": 0}),
    "tone": (TONE.replace("TODAY_DATE", TODAY_DATE), {"professional": 1, "unprofessional": 0}),
    "itinerary_accuracy": (ITINERARY, {"accurate": 1, "inaccurate": 0}),
}


def _reference(calls: list) -> str:
    return json.dumps([{"tool": c["name"], "args": c["args"], "result": c["result"]} for c in calls], indent=1)


def run_judges(turns: pd.DataFrame) -> dict[str, dict[str, dict]]:
    """turns: gate-passed rows from fetch_turns(). Returns {span_id: {judge: {label, score, explanation}}}."""
    if turns.empty:
        return {}
    llm = LLM(provider="google", model=JUDGE_MODEL, api_key=os.environ["GOOGLE_API_KEY"])
    df = turns.assign(reference=(turns["context_calls"] + turns["tool_calls"]).map(_reference)).reset_index(drop=True)
    out: dict[str, dict] = {sid: {} for sid in df["span_id"]}
    for name, (template, choices) in JUDGES.items():
        rows = df[df["input"].map(is_itinerary)] if name == "itinerary_accuracy" else df
        if rows.empty:
            continue
        evaluator = ClassificationEvaluator(name=name, prompt_template=template, llm=llm, choices=choices)
        res = evaluate_dataframe(dataframe=rows, evaluators=[evaluator], exit_on_error=False, max_retries=3)
        for sid, verdict in zip(rows["span_id"], res[f"{name}_score"]):
            if isinstance(verdict, dict) and verdict.get("label"):
                out[sid][name] = {"label": verdict["label"], "score": verdict["score"], "explanation": verdict.get("explanation", "")}
    return out
