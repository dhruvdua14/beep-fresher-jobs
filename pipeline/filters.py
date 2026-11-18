"""
Cheap rule-based filters that run BEFORE the LLM.

Why rules first? Most fetched posts are senior roles or outside India.
Throwing those away with a regex costs nothing; sending them to the LLM
would cost tokens. The LLM then double-checks the survivors.
"""

import re

# ---------------------------------------------------------------- India?

INDIA_WORDS = [
    "india", "bengaluru", "bangalore", "mumbai", "bombay", "delhi", "new delhi",
    "gurugram", "gurgaon", "noida", "hyderabad", "secunderabad", "pune", "chennai",
    "madras", "kolkata", "calcutta", "ahmedabad", "jaipur", "kochi", "cochin",
    "chandigarh", "mohali", "indore", "coimbatore", "thiruvananthapuram",
    "trivandrum", "lucknow", "bhubaneswar", "nagpur", "vadodara", "surat",
    "mysuru", "mysore", "mangaluru", "visakhapatnam", "goa", "karnataka",
    "maharashtra", "telangana", "tamil nadu", "haryana", "uttar pradesh",
]
INDIA_RE = re.compile(r"\b(" + "|".join(INDIA_WORDS) + r")\b", re.I)


def is_india(post):
    # \b stops "Indiana" from matching "india"
    return bool(INDIA_RE.search(post.get("location") or ""))


# ---------------------------------------------------------------- Fresher?

# Title says it's an internship / training role: always keep.
# (Associate Product Manager is the classic campus PM role, so it lives here too.)
INTERN_TITLE = re.compile(
    r"\b(intern|internship|trainee|apprentice|co-?op|associate product manager|apm)\b", re.I)

# Title says it's senior: drop (unless it's an internship, checked first).
SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|manager|director|head|vp|vice president|"
    r"architect|chief|expert|specialist ii|ii|iii|iv|sde[- ]?[2-4]|l[4-9])\b", re.I)

# Title says it's entry level.
JUNIOR_TITLE = re.compile(
    r"\b(fresher|graduate|grad|new grad|entry[- ]level|junior|jr\.?|campus|"
    r"associate(?! (director|manager|vice|principal|partner))|"
    r"sde[- ]?(1|i)|engineer[- ](1|i)|analyst[- ](1|i))\b", re.I)

# Description mentions a 0-to-N years range, or fresher wording.
FRESHER_TEXT = re.compile(
    r"(\b0\s*(-|to|–)\s*[12]\s*(\+\s*)?(years?|yrs?)\b|\bfreshers?\b|recent graduates?|"
    r"\b(class of|batch of|graduating in)\s*20(2[5-8])|\b20(2[5-8])\s*(batch|graduates|pass[- ]?outs?))",
    re.I)

# Description demands 2+ years: not a fresher job.
NEEDS_EXPERIENCE = re.compile(r"\b([2-9]|1[0-9])\s*\+?\s*(-|to|–)?\s*\d*\s*\+?\s*(years|yrs)", re.I)


def fresher_reason(post):
    """
    Return a short reason string if the post MIGHT be entry-level, else None.
    Reasons starting with "unclear" are decided by the LLM's `level` answer.
    """
    title = post.get("title") or ""
    desc = post.get("description") or ""

    if INTERN_TITLE.search(title):
        return "title:intern"
    if SENIOR_TITLE.search(title):
        return None
    if JUNIOR_TITLE.search(title):
        return None if NEEDS_EXPERIENCE.search(desc) and not FRESHER_TEXT.search(desc) else "title:junior"
    if FRESHER_TEXT.search(desc):
        return "description:0-1yrs"
    if post.get("hint_level"):
        return f"platform:{post['hint_level']}"
    if NEEDS_EXPERIENCE.search(desc):
        return None
    # Not senior, but no clear entry-level signal either (e.g. "Software Engineer"
    # with no experience mentioned). Rules can't decide, so the LLM does.
    return "unclear:ask-llm"
