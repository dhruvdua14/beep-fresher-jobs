"""
The daily pipeline. GitHub Actions runs this once a day:

    fetch  ->  India + fresher filter  ->  dedupe  ->  LLM tag  ->  publish JSON

Run it yourself with:
    pip install -r requirements.txt
    GEMINI_API_KEY=... python pipeline/run.py
"""

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))  # so "import config" works from anywhere

import config
from dedupe import dedupe
from filters import fresher_reason, is_india
from sources import enrich_descriptions, fetch_all
from tagger import cost_usd, price, tag_posts

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data"          # pipeline memory, committed back to the repo
PUBLIC = ROOT / "site" / "data"  # what the website reads
IST = timezone(timedelta(hours=5, minutes=30))


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def keep_adzuna_archive(raw, today):
    """
    Adzuna's free plan has a tiny call quota, so we can't re-fetch it every day.
    Instead we remember every Adzuna post we've seen and keep listing it until it's
    30 days old (the same window we ask Adzuna for). Other sources are re-fetched
    daily, so a post that's been filled simply disappears.
    """
    path = STATE / "adzuna_archive.json"
    archive = {p["url"]: p for p in load(path, [])}
    for p in raw:
        if p["source"] == "adzuna":
            archive[p["url"]] = p
    cutoff = (datetime.fromisoformat(today) - timedelta(days=config.ADZUNA_MAX_DAYS_OLD)).date().isoformat()
    archive = {u: p for u, p in archive.items() if (p.get("posted_at") or today) >= cutoff}
    save(path, list(archive.values()))
    return [p for p in raw if p["source"] != "adzuna"] + list(archive.values())


def main():
    now = datetime.now(IST)
    today = now.date().isoformat()

    # 1. FETCH ---------------------------------------------------------------
    print("1. fetching")
    if len(sys.argv) > 2 and sys.argv[1] == "--from-file":   # offline testing
        raw = json.loads(Path(sys.argv[2]).read_text())
        by_source, boards = dict(Counter(p["source"] for p in raw)), {}
    else:
        raw, by_source, boards = fetch_all()
    raw = keep_adzuna_archive(raw, today)
    live_boards = [b for b, n in boards.items() if n]
    print(f"   {len(raw)} posts from {len(live_boards)} of {len(boards)} boards: {by_source}")

    # 2. FILTER --------------------------------------------------------------
    india = [p for p in raw if is_india(p)]
    # Some APIs only give descriptions per post. Fetch those now, but only for
    # India posts whose title isn't obviously senior: a few hundred calls, not thousands.
    n = enrich_descriptions([p for p in india if fresher_reason(p)])
    print(f"   fetched {n} missing descriptions")
    fresher = []
    for p in india:
        reason = fresher_reason(p)
        if reason:
            p["why_fresher"] = reason
            fresher.append(p)
    print(f"2. {len(india)} in India, {len(fresher)} look entry-level")

    # 3. DEDUPE --------------------------------------------------------------
    unique, exact_dupes, fuzzy_dupes = dedupe(fresher)
    print(f"3. removed {exact_dupes} exact + {fuzzy_dupes} fuzzy duplicates -> {len(unique)}")

    # 4. TAG -----------------------------------------------------------------
    print("4. tagging with Gemini")
    cache = load(STATE / "tag_cache.json", {})
    usage = tag_posts(unique, cache)
    save(STATE / "tag_cache.json", cache)
    run_cost = cost_usd(usage)
    print(f"   {usage}  cost ${run_cost:.5f}")

    # The LLM is the second gate: drop anything it says needs experience.
    # A post the rules couldn't decide on is only listed once the LLM says it's
    # entry-level. Clear entry-level posts are listed even if tagging failed.
    def listed(p):
        if p["level"] == "Not fresher":
            return False
        return not (p["level"] == "Unknown" and p["why_fresher"].startswith("unclear"))
    rejected_by_llm = [p for p in unique if p["level"] == "Not fresher"]
    jobs = [p for p in unique if listed(p)]

    # Remember when we first saw each post, for the "New" marker.
    first_seen = load(STATE / "first_seen.json", {})
    for p in jobs:
        p["first_seen"] = first_seen.setdefault(p["id"], today)
    save(STATE / "first_seen.json", first_seen)

    # Newest posting date first (fall back to the day we first saw it).
    jobs.sort(key=lambda p: (p.get("posted_at") or p["first_seen"], p["first_seen"]), reverse=True)

    # 5. PUBLISH -------------------------------------------------------------
    keep = ["id", "title", "company", "location", "cities", "role", "level",
            "confidence", "url", "source", "posted_at", "first_seen"]
    save(PUBLIC / "jobs.json", {
        "updated_at": now.isoformat(timespec="minutes"),
        "count": len(jobs),
        "jobs": [{k: p.get(k) for k in keep} for p in jobs],
    })

    # Spreadsheet copy for the submission doc / Google Sheets import.
    with open(PUBLIC / "jobs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(keep)
        for p in jobs:
            w.writerow([" | ".join(p[k]) if isinstance(p.get(k), list) else p.get(k) for k in keep])

    # Run history: one line per run, used for cost-per-1,000 on /stats.
    run = {
        "date": today, "time": now.strftime("%H:%M"),
        "fetched": len(raw), "india": len(india), "fresher_rules": len(fresher),
        "exact_dupes": exact_dupes, "fuzzy_dupes": fuzzy_dupes,
        "rejected_by_llm": len(rejected_by_llm), "published": len(jobs),
        "newly_tagged": usage["tagged"], "from_cache": usage["from_cache"],
        "llm_calls": usage["calls"], "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"], "cost_usd": round(run_cost, 6),
        "model": usage.get("model"),
        "boards": len(live_boards), "by_source": by_source,
    }
    # Which boards answered and how many entry-level India posts each gave.
    # Used to prune dead slugs from config.py.
    useful = Counter(f"{p['source']}:{p['company']}" for p in jobs)
    save(STATE / "boards.json", {"answered": boards, "listed_per_company": useful.most_common()})

    history = load(STATE / "runs.json", [])
    history.append(run)
    save(STATE / "runs.json", history[-60:])

    # Totals across every run, so the cost figure is based on as many posts as possible.
    tot_tagged = sum(r["newly_tagged"] for r in history)
    tot_cost = sum(r["cost_usd"] for r in history)
    tot_in = sum(r["input_tokens"] for r in history)
    tot_out = sum(r["output_tokens"] for r in history)

    model = usage.get("model") or next((c.get("model") for c in cache.values()), None)
    save(PUBLIC / "stats.json", {
        "updated_at": now.isoformat(timespec="minutes"),
        "model": model,
        "price": {"input_per_m": price(model)[0], "output_per_m": price(model)[1],
                  "usd_to_inr": config.USD_TO_INR},
        "latest": run,
        "cost": {
            "posts_tagged_all_time": tot_tagged,
            "input_tokens": tot_in, "output_tokens": tot_out, "usd_all_time": round(tot_cost, 6),
            "usd_per_1000": round(tot_cost / tot_tagged * 1000, 4) if tot_tagged else None,
            "tokens_per_post": round((tot_in + tot_out) / tot_tagged) if tot_tagged else None,
        },
        "by_role": Counter(p["role"] for p in jobs).most_common(),
        "by_city": Counter(c for p in jobs for c in (p["cities"] or ["Unknown"])).most_common(),
        "by_level": Counter(p["level"] for p in jobs).most_common(),
        "by_company": Counter(p["company"] for p in jobs).most_common(15),
        "by_source": Counter(p["source"] for p in jobs).most_common(),
        "history": history[-30:],
        # Filled in by eval/score.py after the 50-post hand check.
        "eval": load(PUBLIC / "eval.json", {}).get("summary"),
    })
    print(f"5. published {len(jobs)} jobs")


if __name__ == "__main__":
    main()
