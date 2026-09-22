"""Build the blind human-labeling sheet from baseline turns (no judge verdicts included).

    python scripts/make_review_sheet.py [project]

Output: evals/golden/golden.csv — fill in `your_groundedness` and `your_tone`.
Fallback turns are excluded (deterministically failed; nothing for a judge to grade).
Re-running keeps any labels already entered (matched by span_id).
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.deterministic import _fix  # noqa: E402
from evals.turns import fetch_turns  # noqa: E402

project = sys.argv[1] if len(sys.argv) > 1 else "travel-agent-baseline"
out = Path(__file__).resolve().parent.parent / "evals" / "golden" / "golden.csv"

turns = fetch_turns(project, only_unscored=False)
turns = turns[~turns["fallback"]].reset_index(drop=True)


def fmt(calls, mark):
    lines = []
    for c in calls:
        res = json.dumps(_fix(c["result"]), ensure_ascii=False)
        lines.append(f"{mark}{c['name']}({json.dumps(c['args'], ensure_ascii=False)}) -> {res[:700]}")
    return "\n".join(lines)


kept = {}
if out.exists():
    with out.open(newline="", encoding="utf-8-sig") as f:
        kept = {r["span_id"]: r for r in csv.DictReader(f)}

with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["id", "span_id", "user_query", "tool_results", "agent_reply", "your_groundedness", "your_tone", "notes"])
    for i, t in turns.iterrows():
        parts = [fmt(t["context_calls"], "[earlier turn] "), fmt(t["tool_calls"], "")]
        tools = "\n".join(p for p in parts if p) or "(no tools called)"
        old = kept.get(t["span_id"], {})
        w.writerow([i + 1, t["span_id"], t["input"], tools, t["output"],
                    old.get("your_groundedness", ""), old.get("your_tone", ""), old.get("notes", "")])
print(f"wrote {len(turns)} rows -> {out}")
