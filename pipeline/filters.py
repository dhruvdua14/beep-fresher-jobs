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
    "maharashtra", "telangana", "tamil nadu", "haryana", "uttar pradesh", "gujarat",
    "rajasthan", "kerala", "punjab", "west bengal", "odisha", "madhya pradesh", "andhra pradesh",
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
    r"\b(senior|sr\.?|lead|leader|principal|staff|manager|director|head|vp|vice president|specialist|"
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

# "2+ years of experience", "1-2 yrs experience", "experience: 3 to 5 years"...
EXP_AFTER = re.compile(
    r"(\d{1,2})(?:\s*(?:-|–|to)\s*\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b[^.\n]{0,40}?\b(?:experience|exp|work)", re.I)
EXP_BEFORE = re.compile(
    r"\b(?:experience|exp)\b[^.\n]{0,30}?(\d{1,2})(?:\s*(?:-|–|to)\s*\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.I)


def min_years(text):
    """Smallest 'years of experience' the post asks for, or None if it never says."""
    found = [int(m.group(1)) for r in (EXP_AFTER, EXP_BEFORE) for m in r.finditer(text or "")]
    found = [n for n in found if n <= 15]  # ignore "founded 25 years ago" style numbers
    return min(found) if found else None


# Not real openings: talent pools, "general application" posts, placeholders.
NOT_A_JOB = re.compile(r"talent (community|pool|network)|general application|apply here|"
                       r"enthusiast\?|test (employee|job|posting)|work from home job|"
                       r"\bdata entry\b.*\b(phone|android|mobile|home)\b", re.I)


def fresher_reason(post):
    """
    Return a short reason string if the post MIGHT be entry-level, else None.
    Reasons starting with "unclear" are decided by the LLM's `level` answer.
    """
    title = post.get("title") or ""
    desc = post.get("description") or ""

    if NOT_A_JOB.search(title):
        return None
    if INTERN_TITLE.search(title):
        return "title:intern"
    if SENIOR_TITLE.search(title):
        return None
    if JUNIOR_TITLE.search(title):
        return None if (min_years(desc) or 0) >= 2 and not FRESHER_TEXT.search(desc) else "title:junior"
    if FRESHER_TEXT.search(desc):
        return "description:0-1yrs"
    if post.get("hint_level"):
        return f"platform:{post['hint_level']}"
    if (min_years(desc) or 0) >= 2:
        return None  # asks for 2+ years: not for freshers
    # Not senior, but no clear entry-level signal either (e.g. "Software Engineer"
    # with no experience mentioned). Rules can't decide, so the LLM does.
    return "unclear:ask-llm"
