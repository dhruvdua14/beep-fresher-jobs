"""
Fetchers: one small function per hiring platform.

Each fetcher returns a list of "posts" in ONE common shape, so the rest of the
pipeline never needs to know where a post came from:

    {
        "source":      "greenhouse",
        "company":     "Postman",
        "title":       "Software Engineer Intern",
        "location":    "Bengaluru, India",      # raw text, as the company wrote it
        "url":         "https://...",           # link to apply
        "description": "plain text ...",        # trimmed, HTML removed
        "posted_at":   "2026-11-10",            # or None
        "hint_level":  "internship"             # only if the platform tells us
    }
"""

import html
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

import config

HEADERS = {"User-Agent": "beep-fresher-jobs/1.0 (public job-board API client)"}
TIMEOUT = 20
DESC_CHARS = 8000  # enough to reach the "requirements" section, where experience is stated


# ---------------------------------------------------------------- helpers

def get_json(url, params=None):
    """GET a URL and return parsed JSON, or None on any error (logged)."""
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 404:
                return None  # wrong slug / company left the platform
            if r.status_code == 429:  # rate limited: back off and retry
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # network blip: retry, then give up quietly
            if attempt == 2:
                print(f"   ! {url} failed: {e}")
            time.sleep(2)
    return None


def clean_html(text):
    """Turn an HTML job description into short plain text."""
    if not text:
        return ""
    text = html.unescape(html.unescape(text))      # Greenhouse double-escapes
    text = re.sub(r"<(script|style).*?</\1>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:DESC_CHARS]


def pretty(slug):
    """'rebel-foods' -> 'Rebel Foods' (used when an API gives no company name)."""
    return re.sub(r"[-_]+", " ", slug).title()


def iso_date(value):
    """Accept ISO strings or epoch-milliseconds and return 'YYYY-MM-DD'."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
        return str(value)[:10]
    except Exception:
        return None


# ---------------------------------------------------------------- Greenhouse
# Docs: https://developers.greenhouse.io/job-board.html

def fetch_greenhouse(token):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    params={"content": "true"})
    if not data:
        return []
    board = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}") or {}
    company = board.get("name") or pretty(token)
    posts = []
    for j in data.get("jobs", []):
        posts.append({
            "source": "greenhouse",
            "company": company,
            "title": j.get("title", "").strip(),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url"),
            "description": clean_html(j.get("content")),
            "posted_at": iso_date(j.get("first_published") or j.get("updated_at")),
        })
    return posts


# ---------------------------------------------------------------- Lever
# Docs: https://github.com/lever/postings-api

def fetch_lever(slug):
    data = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    if not isinstance(data, list):
        return []
    posts = []
    for j in data:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        posts.append({
            "source": "lever",
            "company": pretty(slug),
            "title": j.get("text", "").strip(),
            "location": " / ".join(l for l in locs if l),
            "url": j.get("hostedUrl"),
            "description": (j.get("descriptionPlain") or "")[:DESC_CHARS],
            "posted_at": iso_date(j.get("createdAt")),
            "hint_level": "internship" if "intern" in (cats.get("commitment") or "").lower() else None,
        })
    return posts


# ---------------------------------------------------------------- Ashby
# Docs: https://developers.ashbyhq.com/docs/public-job-posting-api

def fetch_ashby(slug):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not data:
        return []
    posts = []
    for j in data.get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        posts.append({
            "source": "ashby",
            "company": pretty(slug),
            "title": j.get("title", "").strip(),
            "location": " / ".join(l for l in locs if l),
            "url": j.get("jobUrl"),
            "description": (j.get("descriptionPlain") or "")[:DESC_CHARS],
            "posted_at": iso_date(j.get("publishedAt")),
            "hint_level": "internship" if (j.get("employmentType") or "").lower() == "intern" else None,
        })
    return posts


# ---------------------------------------------------------------- SmartRecruiters
# Docs: https://developers.smartrecruiters.com/docs/posting-api

def fetch_smartrecruiters(company_id):
    posts, offset = [], 0
    while offset < 500:  # safety cap
        data = get_json(f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings",
                        params={"country": "in", "limit": 100, "offset": offset})
        if not data or not data.get("content"):
            break
        for j in data["content"]:
            loc = j.get("location") or {}
            level = ((j.get("experienceLevel") or {}).get("id") or "").lower()
            posts.append({
                "source": "smartrecruiters",
                "company": (j.get("company") or {}).get("name") or company_id,
                "title": j.get("name", "").strip(),
                "location": loc.get("fullLocation") or ", ".join(
                    x for x in [loc.get("city"), loc.get("region"), "India"] if x),
                "url": f"https://jobs.smartrecruiters.com/{company_id}/{j.get('id')}",
                # The list endpoint has no description. We fetch it later, only for
                # posts that survive the cheap filters (see enrich_descriptions).
                "description": "",
                "detail_url": f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings/{j.get('id')}",
                "posted_at": iso_date(j.get("releasedDate")),
                # Only trust "internship". Some companies mark nearly every job "entry_level".
                "hint_level": "internship" if level == "internship" else None,
            })
        offset += 100
        if offset >= data.get("totalFound", 0):
            break
    return posts


# ---------------------------------------------------------------- Workable
# Public careers-page widget API: apply.workable.com/api/v1/widget/accounts/<slug>

def fetch_workable(slug):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
                    params={"details": "true"})
    if not data:
        return []
    posts = []
    for j in data.get("jobs", []):
        posts.append({
            "source": "workable",
            "company": data.get("name") or pretty(slug),
            "title": (j.get("title") or "").strip(),
            "location": ", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x),
            "url": j.get("url") or j.get("application_url"),
            "description": clean_html(j.get("description")),
            "posted_at": iso_date(j.get("published_on") or j.get("created_at")),
            "hint_level": {"Internship": "internship", "Entry level": "fresher"}.get(j.get("experience")),
        })
    return posts


# ---------------------------------------------------------------- Recruitee
# Public careers-site API: <slug>.recruitee.com/api/offers/

def fetch_recruitee(slug):
    data = get_json(f"https://{slug}.recruitee.com/api/offers/")
    if not data:
        return []
    posts = []
    for j in data.get("offers", []):
        posts.append({
            "source": "recruitee",
            "company": j.get("company_name") or pretty(slug),
            "title": (j.get("title") or "").strip(),
            "location": ", ".join(x for x in [j.get("city"), j.get("country")] if x) or j.get("location", ""),
            "url": j.get("careers_url"),
            "description": clean_html(j.get("description")),
            "posted_at": iso_date(j.get("published_at") or j.get("created_at")),
            "hint_level": "internship" if (j.get("employment_type_code") or "").startswith("intern") else None,
        })
    return posts


# ---------------------------------------------------------------- The Muse
# Public API, no key needed for light use: https://www.themuse.com/developers/api/v2
# It can filter by city AND level, so we ask directly for entry-level/intern jobs.

def fetch_themuse():
    posts = []
    params = [("location", c) for c in config.MUSE_LOCATIONS] + \
             [("level", "Entry Level"), ("level", "Internship")]
    for page in range(config.MUSE_MAX_PAGES):
        data = get_json("https://www.themuse.com/api/public/jobs", params=params + [("page", page)])
        results = (data or {}).get("results") or []
        for j in results:
            locs = [l.get("name", "") for l in j.get("locations") or []]
            levels = [l.get("name", "") for l in j.get("levels") or []]
            posts.append({
                "source": "themuse",
                "company": (j.get("company") or {}).get("name", "Unknown"),
                "title": (j.get("name") or "").strip(),
                "location": " / ".join(locs),
                "url": (j.get("refs") or {}).get("landing_page"),
                "description": clean_html(j.get("contents")),
                "posted_at": iso_date(j.get("publication_date")),
                "hint_level": "internship" if "Internship" in levels else None,
            })
        if not results or page + 1 >= (data or {}).get("page_count", 0):
            break
        time.sleep(0.5)
    return posts


# ---------------------------------------------------------------- Adzuna (India, optional)
# Docs: https://developer.adzuna.com  (free key; their terms ask for attribution,
# which is in the site footer)

def fetch_adzuna():
    # .strip(): a secret pasted with a trailing newline broke auth (see BUILDING_LOG)
    app_id = (os.getenv("ADZUNA_APP_ID") or "").strip()
    app_key = (os.getenv("ADZUNA_APP_KEY") or "").strip()
    if not (app_id and app_key):
        print("   (no Adzuna key set, skipping Adzuna)")
        return []
    posts, calls = [], 0
    day = datetime.now(timezone.utc).timetuple().tm_yday
    k = config.ADZUNA_MAX_CALLS_PER_RUN
    todays = [config.ADZUNA_QUERIES[(day * k + i) % len(config.ADZUNA_QUERIES)] for i in range(k)]
    for q in todays:
        for page in range(1, config.ADZUNA_PAGES_PER_QUERY + 1):
            if calls >= config.ADZUNA_MAX_CALLS_PER_RUN:
                return posts  # protect the tiny free quota
            calls += 1
            data = get_json(f"https://api.adzuna.com/v1/api/jobs/in/search/{page}", params={
                "app_id": app_id, "app_key": app_key, "what_or": q,
                "results_per_page": 50, "max_days_old": config.ADZUNA_MAX_DAYS_OLD,
                "content-type": "application/json",
            })
            results = (data or {}).get("results") or []
            for j in results:
                posts.append({
                    "source": "adzuna",
                    "company": (j.get("company") or {}).get("display_name", "Unknown"),
                    "title": clean_html(j.get("title")),
                    "location": (j.get("location") or {}).get("display_name", "") + ", India",
                    "url": j.get("redirect_url"),
                    "description": clean_html(j.get("description")),
                    "posted_at": iso_date(j.get("created")),
                })
            if len(results) < 50:
                break
            time.sleep(1)  # be polite
    return posts


# ---------------------------------------------------------------- run all

def enrich_descriptions(posts):
    """Fill in descriptions for posts whose list API had none (SmartRecruiters)."""
    todo = [p for p in posts if p.get("detail_url") and not p["description"]]

    def one(p):
        data = get_json(p["detail_url"]) or {}
        sections = ((data.get("jobAd") or {}).get("sections") or {})
        text = " ".join((sections.get(k) or {}).get("text", "")
                        for k in ["jobDescription", "qualifications", "additionalInformation"])
        p["description"] = clean_html(text)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, todo))
    return len(todo)


def fetch_all():
    """Fetch every source in parallel. Returns (posts, posts_per_source, posts_per_board)."""
    # Every slug is tried on all three big platforms, because companies switch
    # platforms and we don't always know which one they use today.
    slugs = sorted(set(config.GREENHOUSE + config.LEVER + config.ASHBY + config.ANY_PLATFORM))
    jobs = ([(fetch_greenhouse, s) for s in slugs] +
            [(fetch_lever, s) for s in slugs] +
            [(fetch_ashby, s) for s in slugs] +
            [(fetch_smartrecruiters, s) for s in config.SMARTRECRUITERS] +
            [(fetch_workable, s) for s in config.WORKABLE] +
            [(fetch_recruitee, s) for s in config.RECRUITEE])

    posts, live_boards = [], {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(lambda job: (job, job[0](job[1])), jobs)
        for (fn, slug), found in results:
            # remember which boards answered, and with how many posts
            live_boards[f"{fn.__name__.replace('fetch_', '')}:{slug}"] = len(found)
            posts.extend(found)

    muse = fetch_themuse()
    live_boards["themuse"] = len(muse)
    posts.extend(muse)
    posts.extend(fetch_adzuna())

    counts = {}
    for p in posts:
        counts[p["source"]] = counts.get(p["source"], 0) + 1
    return posts, counts, live_boards
