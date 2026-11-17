"""
Read the hand-checked eval/hand_check.csv and compute accuracy.
Writes site/data/eval.json, which the /stats page displays.

Accuracy = rows marked Y / rows that were checked (blank rows are skipped).
"Both correct" counts a post as right only if role AND city are right.
"""
import csv, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "eval/hand_check.csv", encoding="utf-8")))
yes = lambda v: v.strip().upper().startswith("Y")
checked = lambda col: [r for r in rows if r[col].strip()]

def acc(col):
    done = checked(col)
    return {"correct": sum(yes(r[col]) for r in done), "checked": len(done),
            "pct": round(100 * sum(yes(r[col]) for r in done) / len(done), 1) if done else None}

both = [r for r in rows if r["role_ok"].strip() and r["city_ok"].strip()]
both_ok = sum(yes(r["role_ok"]) and yes(r["city_ok"]) for r in both)

# Which mistakes happen most? e.g. "Data & Analytics -> AI / ML"
confusions = Counter(f'{r["llm_role"]} -> {r["correct_role"] or "?"}'
                     for r in checked("role_ok") if not yes(r["role_ok"]))
city_errors = [{"title": r["title"], "location_raw": r["location_raw"], "llm": r["llm_cities"],
                "correct": r["correct_cities"]} for r in checked("city_ok") if not yes(r["city_ok"])]

# Is the model's confidence score useful? Compare accuracy above/below 0.8.
def band(lo, hi):
    rs = [r for r in checked("role_ok") if r["llm_confidence"] and lo <= float(r["llm_confidence"]) < hi]
    return {"n": len(rs), "role_pct": round(100 * sum(yes(r["role_ok"]) for r in rs) / len(rs), 1) if rs else None}

summary = {"sample_size": len(rows), "role": acc("role_ok"), "city": acc("city_ok"),
           "level": acc("level_ok"),
           "both": {"correct": both_ok, "checked": len(both),
                    "pct": round(100 * both_ok / len(both), 1) if both else None}}
out = {"summary": summary, "role_confusions": confusions.most_common(),
       "city_errors": city_errors,
       "confidence": {"high (>=0.8)": band(0.8, 1.01), "low (<0.8)": band(0, 0.8)}}
(ROOT / "site/data/eval.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps(out, indent=1, ensure_ascii=False))
