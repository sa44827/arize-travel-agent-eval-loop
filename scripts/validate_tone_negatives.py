"""Test the tone judge's negative class specifically.

The real golden set (evals/golden/golden.csv) has zero unprofessional-labeled
turns, because the fixed agent doesn't currently produce bad tone -- so a judge
that always said "professional" would score 100% on it. This script runs the
same tone judge against 4 synthetic, deliberately-unprofessional replies
(evals/golden/tone_negative_examples.csv) to test whether it actually catches
the failure class it exists to catch.

    python scripts/validate_tone_negatives.py
"""

import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.judges import JUDGES, LLM, JUDGE_MODEL  # noqa: E402
from phoenix.evals import ClassificationEvaluator, evaluate_dataframe  # noqa: E402
import os  # noqa: E402

rows = list(csv.DictReader((Path(__file__).resolve().parent.parent / "evals/golden/tone_negative_examples.csv").open(encoding="utf-8-sig")))
df = pd.DataFrame([{"input": r["user_query"], "output": r["agent_reply"]} for r in rows])

template, choices = JUDGES["tone"]
llm = LLM(provider="google", model=JUDGE_MODEL, api_key=os.environ["GOOGLE_API_KEY"])
evaluator = ClassificationEvaluator(name="tone", prompt_template=template, llm=llm, choices=choices)
res = evaluate_dataframe(dataframe=df, evaluators=[evaluator], exit_on_error=False, max_retries=3)

correct = 0
for i, r in enumerate(rows):
    verdict = res["tone_score"].iloc[i]
    judge_label = verdict["label"] if isinstance(verdict, dict) else "ERROR"
    ok = judge_label == r["your_tone"].strip()
    correct += ok
    print(f"row {r['id']} [{r['notes']}]")
    print(f"  human={r['your_tone']}  judge={judge_label}  {'OK' if ok else 'MISS'}")
    if isinstance(verdict, dict):
        print(f"  judge said: {verdict.get('explanation','')[:200]}")

print(f"\n=== tone negative-class: {correct}/{len(rows)} caught = {correct/len(rows):.0%}")
