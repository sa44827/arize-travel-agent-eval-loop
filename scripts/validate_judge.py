"""Judge validation: run the LLM judges on the golden turns and measure agreement with human labels.

    python scripts/validate_judge.py [project]

Compares groundedness and tone against evals/golden/golden.csv (your_groundedness, your_tone).
Rows with a blank label are skipped. Prints agreement %, Cohen's kappa, and every disagreement.
Judge target: 75-90% agreement before we trust it to gate or alert.
"""

import csv
import sys
from collections import Counter
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.judges import run_judges  # noqa: E402
from evals.turns import fetch_turns  # noqa: E402

project = sys.argv[1] if len(sys.argv) > 1 else "travel-agent-baseline"
golden = list(csv.DictReader((Path(__file__).resolve().parent.parent / "evals/golden/golden.csv").open(encoding="utf-8-sig")))
by_span = {r["span_id"]: r for r in golden}

turns = fetch_turns(project, only_unscored=False)
turns = turns[turns["span_id"].isin(by_span)].reset_index(drop=True)
verdicts = run_judges(turns)


def kappa(pairs):
    n = len(pairs)
    po = sum(h == j for h, j in pairs) / n
    hc, jc = Counter(h for h, _ in pairs), Counter(j for _, j in pairs)
    pe = sum(hc[k] * jc[k] for k in set(hc) | set(jc)) / n**2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


ALLOWED = {"groundedness": ["grounded", "ungrounded"], "tone": ["professional", "unprofessional"]}


def clean(label, judge, row_id):
    """Match a hand-typed label to a valid one; warn on typos, skip the unmatchable."""
    label = label.strip().lower()
    if label in ALLOWED[judge] or not label:
        return label
    close = get_close_matches(label, ALLOWED[judge], n=1, cutoff=0.7)
    print(f"  WARNING row {row_id}: {judge} label '{label}' is not valid -> " + (f"treating as '{close[0]}'" if close else "skipped"))
    return close[0] if close else ""


for judge, col in (("groundedness", "your_groundedness"), ("tone", "your_tone")):
    pairs, misses = [], []
    for sid, row in by_span.items():
        human = clean(row[col], judge, row["id"])
        verdict = verdicts.get(sid, {}).get(judge)
        if not human or not verdict:
            continue
        pairs.append((human, verdict["label"]))
        if human != verdict["label"]:
            misses.append((row["id"], row["user_query"][:50], human, verdict["label"], verdict["explanation"][:220], row["notes"].strip()))
    agree = sum(h == j for h, j in pairs)
    print(f"\n=== {judge}: agreement {agree}/{len(pairs)} = {agree / max(len(pairs), 1):.0%}  kappa={kappa(pairs):.2f}")
    print("    human:", dict(Counter(h for h, _ in pairs)), "| judge:", dict(Counter(j for _, j in pairs)))
    for m in misses:
        print(f"  row {m[0]:>2} [{m[1]}] human={m[2]} judge={m[3]}\n      judge said: {m[4]}" + (f"\n      your note: {m[5]}" if m[5] else ""))
