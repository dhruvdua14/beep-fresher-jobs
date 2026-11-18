"""
LLM tagging with Google Gemini (free tier).

For each post the model returns:
    role        exactly one value from config.ROLES
    cities      one or more values from config.CITIES
    level       "Internship" | "Fresher" | "Early career" | "Not fresher"   (second filter gate)
    confidence  0.0 - 1.0, the model's own certainty

Three things keep this cheap and reliable:
1. BATCHING: 40 posts go in one request, so the long instructions are paid
   for once per 40 posts instead of once per post.
2. A JSON SCHEMA with enums: Gemini is *forced* to answer with a valid role
   and city from our lists, so we never have to parse free text.
3. A CACHE: a post tagged yesterday is not tagged again today. Only new
   posts cost tokens.
"""

import json
import os
import re
import time

import requests

import config

# Bump this whenever the prompt or the input format changes: cached tags made
# with an older version are thrown away and those posts are tagged again.
PROMPT_VERSION = 6

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# The full prompt is kept here, in plain sight, so it can be shown in the
# submission doc and changed live.
PROMPT = f"""You label Indian job posts for a job board used by college students.

For EACH post, return:
- "i": the post's number, copied exactly.
- "role": the single best category from this list. Judge by what the person will
  actually do day to day, not by buzzwords in the company name:
  {json.dumps(config.ROLES)}
  Notes: "AI / ML" is only for roles that build or research ML models. A data analyst
  or BI role is "Data & Analytics". Business analyst roles are "Consulting & Strategy"
  unless they are mainly SQL/dashboards. QA/test, DevOps, SRE and mobile roles are
  "Software Engineering". Use "Other" only when nothing fits.
- "cities": every Indian city where the job is based, using ONLY these names:
  {json.dumps(config.CITIES)}
  Map spellings to the list: Bangalore -> Bengaluru, Gurgaon -> Gurugram,
  New Delhi -> Delhi, Bombay -> Mumbai, Trivandrum -> Thiruvananthapuram,
  Cochin -> Kochi. If the job is fully remote in India use "Remote". An Indian city
  that is not in the list is "Other India". If the job is NOT located in India
  (e.g. a US state like "MI" or "CA", or another country), answer ["Not in India"].
- "level":
  "Internship" if it is an internship / trainee / apprenticeship.
  "Fresher" if a new graduate with no experience can clearly apply: the post says
  fresher / new grad / entry level / campus / 0-1 years, or the title is junior-level
  (Associate, Junior, Engineer I, SDE 1, Graduate, Trainee), or the description notes
  it matched a job-board search for "fresher" / "graduate trainee" and nothing in the
  post asks for more experience.
  "Early career" only if the post STATES a requirement of at most 1-2 years
  (e.g. "1+ years", "1-2 years", "0-2 years", "up to 2 years"). Words like Intermediate,
  Consultant, Engineer II or Specialist mean "Not fresher".
  "Not fresher" if it asks for 2+ years minimum, or is a senior / lead / manager /
  specialist role, or it says nothing about experience and has no entry-level signal.
  When unsure, say "Not fresher": a student wasting time on a job they can't get is
  worse than missing one.
  "Not a job" if it is not a specific opening: talent pools / "join our talent community" /
  general applications, test postings, or spammy schemes (pay-to-join, "earn from home
  by typing", data entry on your phone).
- "confidence": a number 0 to 1 for how sure you are about role AND cities together.

Return one object per post, in a JSON array. Nothing else."""

# Gemini "structured output": the response MUST match this shape.
SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "i": {"type": "INTEGER"},
            "role": {"type": "STRING", "enum": config.ROLES},
            "cities": {"type": "ARRAY", "items": {"type": "STRING", "enum": config.CITIES}},
            "level": {"type": "STRING", "enum": config.LEVELS},
            "confidence": {"type": "NUMBER"},
        },
        "required": ["i", "role", "cities", "level", "confidence"],
    },
}


EXPERIENCE_WORDS = re.compile(
    r"(year|yrs|experience|fresher|graduat|entry|junior|intern|batch|degree|b\.?tech|students?)", re.I)


def experience_lines(text, limit=400):
    """The sentences that talk about experience/education. That's where 'fresher or not' is decided."""
    picked = [s.strip() for s in re.split(r"(?<=[.!?•;])\s+", text) if EXPERIENCE_WORDS.search(s)]
    return " … ".join(picked)[:limit]


def format_batch(posts):
    """Short, token-efficient text version of a batch of posts."""
    lines = []
    for i, p in enumerate(posts):
        lines.append(
            f"### Post {i}\nTitle: {p['title']}\nCompany: {p['company']}\n"
            f"Location: {p['location']}\nDescription start: {p['description'][:350]}\n"
            f"Experience lines: {experience_lines(p['description']) or 'none found'}")
    return "\n\n".join(lines)


MODEL = None       # the model currently in use
CANDIDATES = []    # fallbacks, filled by pick_model()


def pick_model():
    """
    Candidate models this key can use, best first. A model can be *listed* and still
    answer 404 (retired for new keys), so call_gemini() moves down this list on 404.
    """
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"pageSize": 200}, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=30)
    r.raise_for_status()
    available = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    print(f"   models this key can use: {[m for m in available if 'gemini' in m]}")
    # Our preference order first, then any other non-preview Flash-Lite / Flash model.
    extra = [m for m in available if "flash" in m and "preview" not in m and "tts" not in m
             and "image" not in m and m not in config.GEMINI_MODELS]
    extra.sort(key=lambda m: "lite" not in m)
    return [m for m in config.GEMINI_MODELS if m in available] + extra


def call_gemini(posts, usage):
    """Tag one batch. Returns {index: tag}. Adds token counts to `usage`."""
    global MODEL
    key = os.environ["GEMINI_API_KEY"]
    body = {
        "systemInstruction": {"parts": [{"text": PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": format_batch(posts)}]}],
        "generationConfig": {
            "temperature": 0,  # same input -> same answer, which makes the eval repeatable
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    for attempt in range(8):
        r = requests.post(API.format(model=MODEL), json=body,
                          headers={"x-goog-api-key": key}, timeout=120)
        if r.status_code == 404 and CANDIDATES:  # model retired: try the next one
            print(f"   {MODEL} answered 404 ({r.text[:120].strip()}); switching to {CANDIDATES[0]}")
            MODEL = CANDIDATES.pop(0)
            usage["model"] = MODEL
            continue
        if r.status_code == 429 and "PerDay" in r.text:
            raise QuotaExhausted()  # daily free quota used up: stop, finish tomorrow
        if r.status_code in (429, 500, 503):  # free-tier rate limit / overload
            wait = 15 * (attempt + 1)
            print(f"   gemini {r.status_code}, waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        meta = data.get("usageMetadata", {})
        usage["calls"] += 1
        usage["input_tokens"] += meta.get("promptTokenCount", 0)
        # thinking tokens are billed as output tokens, so count them too
        usage["output_tokens"] += meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return {item["i"]: item for item in json.loads(text) if 0 <= item.get("i", -1) < len(posts)}
    raise RuntimeError("Gemini kept failing")


class QuotaExhausted(Exception):
    pass


def tag_posts(posts, cache):
    """
    Add role/cities/level/confidence to every post.
    `cache` maps post id -> tag and is updated in place.
    Returns a usage dict with call and token counts for this run.
    """
    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "tagged": 0, "from_cache": 0}
    for k in [k for k, v in cache.items() if v.get("v") != PROMPT_VERSION]:
        del cache[k]  # stale: made with an older prompt
    todo = [p for p in posts if p["id"] not in cache]
    usage["from_cache"] = len(posts) - len(todo)

    if todo and not os.getenv("GEMINI_API_KEY"):
        print("   ! GEMINI_API_KEY not set: new posts stay untagged this run")
        todo = []

    print(f"   {len(todo)} new posts to tag, {usage['from_cache']} already tagged")
    global MODEL, CANDIDATES
    if todo:
        CANDIDATES = pick_model()
        MODEL = CANDIDATES.pop(0)
        usage["model"] = MODEL
        print(f"   model: {MODEL}")
    for start in range(0, len(todo), config.BATCH_SIZE):
        batch = todo[start:start + config.BATCH_SIZE]
        try:
            tags = call_gemini(batch, usage)
        except QuotaExhausted:
            print("   ! free daily quota reached; the rest will be tagged on the next run")
            break
        except Exception as e:  # one bad batch must not kill the daily run
            print(f"   ! batch {start // config.BATCH_SIZE} failed: {e}")
            continue
        for i, p in enumerate(batch):
            t = tags.get(i)
            if t:  # the model occasionally skips an item; it'll be retried tomorrow
                cache[p["id"]] = {
                    "role": t["role"], "cities": t["cities"] or ["Other India"],
                    "level": t["level"], "confidence": round(float(t["confidence"]), 2),
                    "model": MODEL, "v": PROMPT_VERSION,
                }
                usage["tagged"] += 1
        time.sleep(config.SECONDS_BETWEEN_CALLS)

    for p in posts:
        p.update(cache.get(p["id"], {"role": "Untagged", "cities": [], "level": "Unknown", "confidence": None}))
    return usage


def price(model):
    return config.PRICES.get(model, config.DEFAULT_PRICE)


def cost_usd(usage):
    p_in, p_out = price(usage.get("model"))
    return (usage["input_tokens"] * p_in + usage["output_tokens"] * p_out) / 1_000_000
