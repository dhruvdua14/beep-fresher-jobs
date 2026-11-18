"""
Pick 50 published posts at random (fixed seed, so anyone can reproduce the
same sample) and write them to eval/hand_check.csv for manual checking.

How to hand-check: open the CSV in Google Sheets, open each link, and in the
three *_ok columns write Y or N. If N, write the right answer in the
correct_* column next to it. Then run:  python eval/score.py

Note: the committed sheet was drawn on 18 Nov with seed 42. One row (a Marriott post)
turned out to be a duplicate and was removed by the dedupe fix (BUILDING_LOG #17), so it
was swapped for one more random listed post (seed 43). The other 49 rows are unchanged.
"""
import csv, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
jobs = json.loads((ROOT / "site/data/jobs.json").read_text())["jobs"]
jobs = [j for j in jobs if j["role"] != "Untagged"]
sample = random.Random(42).sample(jobs, min(50, len(jobs)))

with open(ROOT / "eval/hand_check.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "title", "company", "location_raw", "url",
                "llm_role", "llm_cities", "llm_level", "llm_confidence",
                "role_ok", "correct_role", "city_ok", "correct_cities",
                "level_ok", "correct_level", "notes"])
    for j in sample:
        w.writerow([j["id"], j["title"], j["company"], j["location"], j["url"],
                    j["role"], " | ".join(j["cities"]), j["level"], j["confidence"],
                    "", "", "", "", "", "", ""])
print(f"wrote {len(sample)} rows to eval/hand_check.csv")
