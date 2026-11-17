"""
LLM tagging with Google Gemini (free tier).

For each post the model returns:
    role        exactly one value from config.ROLES
    cities      one or more values from config.CITIES
    level       "Internship" | "Fresher" | "Not fresher"   (second filter gate)
    confidence  0.0 - 1.0, the model's own certainty

Three things keep this cheap and reliable:
1. BATCHING: 20 posts go in one request, so the long instructions are paid
   for once per 20 posts instead of once per post.
2. A JSON SCHEMA with enums: Gemini is *forced* to answer with a valid role
   and city from our lists, so we never have to parse free text.
3. A CACHE: a post tagged yesterday is not tagged again today. Only new
   posts cost tokens.
"""

import json
import os
import time

import requests

import config

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
  that is not in the list is "Other India".
- "level": "Internship" if it is an internship / trainee / apprenticeship;
  "Fresher" if a new graduate with 0-1 years of experience can apply;
  otherwise "Not fresher" (e.g. it asks for 2+ years, or it is a senior/lead role).
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


def format_batch(posts):
    """Short, token-efficient text version of a batch of posts."""
    lines = []
    for i, p in enumerate(posts):
        lines.append(
            f"### Post {i}\nTitle: {p['title']}\nCompany: {p['company']}\n"
            f"Location: {p['location']}\nDescription: {p['description'][:600]}")
    return "\n\n".join(lines)


def call_gemini(posts, usage):
    """Tag one batch. Returns {index: tag}. Adds token counts to `usage`."""
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
    for attempt in range(5):
        r = requests.post(API.format(model=config.GEMINI_MODEL), json=body,
                          headers={"x-goog-api-key": key}, timeout=120)
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


def tag_posts(posts, cache):
    """
    Add role/cities/level/confidence to every post.
    `cache` maps post id -> tag and is updated in place.
    Returns a usage dict with call and token counts for this run.
    """
    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "tagged": 0, "from_cache": 0}
    todo = [p for p in posts if p["id"] not in cache]
    usage["from_cache"] = len(posts) - len(todo)

    if todo and not os.getenv("GEMINI_API_KEY"):
        print("   ! GEMINI_API_KEY not set: new posts stay untagged this run")
        todo = []

    print(f"   {len(todo)} new posts to tag, {usage['from_cache']} already tagged")
    for start in range(0, len(todo), config.BATCH_SIZE):
        batch = todo[start:start + config.BATCH_SIZE]
        try:
            tags = call_gemini(batch, usage)
        except Exception as e:  # one bad batch must not kill the daily run
            print(f"   ! batch {start // config.BATCH_SIZE} failed: {e}")
            continue
        for i, p in enumerate(batch):
            t = tags.get(i)
            if t:  # the model occasionally skips an item; it'll be retried tomorrow
                cache[p["id"]] = {
                    "role": t["role"], "cities": t["cities"] or ["Other India"],
                    "level": t["level"], "confidence": round(float(t["confidence"]), 2),
                    "model": config.GEMINI_MODEL,
                }
                usage["tagged"] += 1
        time.sleep(config.SECONDS_BETWEEN_CALLS)

    for p in posts:
        p.update(cache.get(p["id"], {"role": "Untagged", "cities": [], "level": "Unknown", "confidence": None}))
    return usage


def cost_usd(usage):
    return (usage["input_tokens"] * config.PRICE_INPUT_PER_M +
            usage["output_tokens"] * config.PRICE_OUTPUT_PER_M) / 1_000_000
