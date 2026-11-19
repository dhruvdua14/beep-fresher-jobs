"""
Save the original text of the 50 hand-check posts to eval/hand_check_text.json,
so a reviewer can judge each tag against exactly what the employer wrote,
without clicking 50 links (some of which expire).

Runs in GitHub Actions (eval.yml), because the job APIs are fetched from there.
Adzuna posts come from our own 30-day archive; the rest are fetched again.
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from dedupe import post_id                                  # noqa: E402
from sources import fetch_all, enrich_descriptions          # noqa: E402

rows = list(csv.DictReader(open(ROOT / "eval/hand_check.csv", encoding="utf-8")))
want = {r["id"] for r in rows}

posts = json.loads((ROOT / "data/adzuna_archive.json").read_text())
fetched, _, _ = fetch_all()
posts += [p for p in fetched if p["source"] != "adzuna"]
by_id = {post_id(p): p for p in posts if post_id(p) in want}
enrich_descriptions(list(by_id.values()))

out = {i: {"title": p["title"], "company": p["company"], "location": p["location"],
           "source": p["source"], "url": p["url"], "description": p.get("description", "")}
       for i, p in by_id.items()}
(ROOT / "eval/hand_check_text.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"saved text for {len(out)} of {len(want)} posts; missing: {sorted(want - set(out))}")
