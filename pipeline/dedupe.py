"""
Remove duplicate posts in two passes.

Pass 1, exact: build a key from normalised company + title + location and
hash it. Same key means the same job, e.g. one company listing the
identical role twice.

Pass 2, fuzzy: catch near-duplicates that exact matching misses, such as
    "Software Engineer Intern - 2026"   vs   "Software Engineer Intern (2026)"
    "Razorpay Software Pvt Ltd"         vs   "Razorpay"
For posts from the same company, compare titles with rapidfuzz. If they are
at least FUZZY_THRESHOLD similar AND the locations overlap, keep only one.
"""

import hashlib
import re

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 92

COMPANY_NOISE = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|technologies|technology|tech|solutions|"
    r"india|software|services|labs|the)\b\.?", re.I)


def norm(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_company(name):
    return norm(COMPANY_NOISE.sub(" ", name or "")) or norm(name)


def post_id(post):
    """Stable id for a post. Also used to remember LLM tags between runs."""
    key = f"{norm_company(post['company'])}|{norm(post['title'])}|{norm(post['location'])}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def dedupe(posts):
    """Return (unique_posts, number_of_exact_dupes, number_of_fuzzy_dupes)."""
    # Pass 1: exact hash. Prefer the first-seen copy, which comes from a
    # company's own careers API, over aggregator copies (Adzuna is fetched last).
    seen, unique = set(), []
    for p in posts:
        p["id"] = post_id(p)
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)
    exact = len(posts) - len(unique)

    # Pass 2: fuzzy, only comparing posts from the same (normalised) company,
    # so this stays fast even with thousands of posts.
    by_company, kept, fuzzy = {}, [], 0
    for p in unique:
        bucket = by_company.setdefault(norm_company(p["company"]), [])
        is_dup = any(
            fuzz.token_sort_ratio(title_key(p["title"]), title_key(q["title"])) >= FUZZY_THRESHOLD
            and locations_overlap(p["location"], q["location"])
            for q in bucket
        )
        if is_dup:
            fuzzy += 1
        else:
            bucket.append(p)
            kept.append(p)
    return kept, exact, fuzzy


# Old and new city names, so "Bangalore" and "Bengaluru" count as the same place.
CITY_ALIASES = {"bangalore": "bengaluru", "gurgaon": "gurugram", "bombay": "mumbai",
                "new delhi": "delhi", "madras": "chennai", "calcutta": "kolkata",
                "trivandrum": "thiruvananthapuram", "cochin": "kochi", "mysore": "mysuru"}
LOCATION_STOP = {"india", "remote", "hybrid", "in", "and", "or", "karnataka", "maharashtra",
                 "telangana", "tamil", "nadu", "haryana", "uttar", "pradesh", "west", "bengal"}


def location_words(text):
    text = norm(text)
    for old, new in CITY_ALIASES.items():
        text = re.sub(rf"\b{old}\b", new, text)
    return set(text.split()) - LOCATION_STOP


def locations_overlap(a, b):
    """True if two raw location strings share a city (or either one is blank)."""
    wa, wb = location_words(a), location_words(b)
    return not wa or not wb or bool(wa & wb)


def title_key(title):
    """Title without years/batch words: "SWE Intern (2026)" == "SWE Intern"."""
    return re.sub(r"\b(20\d\d|batch|summer|winter)\b", " ", norm(title)).strip()
