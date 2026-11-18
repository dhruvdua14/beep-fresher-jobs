# Fresher Ledger: submission notes

Dhruv Dua · Beep, Gen AI & Engineering round

| | |
|---|---|
| **Live tool** | https://dhruvdua14.github.io/beep-fresher-jobs/ |
| **Numbers page** | https://dhruvdua14.github.io/beep-fresher-jobs/stats.html |
| **Repo** | https://github.com/dhruvdua14/beep-fresher-jobs |
| **What broke** | [BUILDING_LOG.md](../BUILDING_LOG.md) (17 entries, written as it happened) |
| **Live data (CSV)** | https://dhruvdua14.github.io/beep-fresher-jobs/data/jobs.csv |
| **Hand-check sheet** | [eval/hand_check.csv](../eval/hand_check.csv) |

> To open the live data as a Google Sheet: new sheet, cell A1:
> `=IMPORTDATA("https://dhruvdua14.github.io/beep-fresher-jobs/data/jobs.csv")`
> It updates itself after every daily run.

---

## 1. What it does

Every morning at 08:00 IST a GitHub Action:

1. **Fetches** about 10,000 posts from public job-board APIs: Greenhouse, Lever, Ashby and
   SmartRecruiters boards of ~300 companies, plus the Adzuna India API. No scraping,
   and nothing from LinkedIn, Naukri or Internshala, whose terms forbid it.
2. **Filters** with cheap rules: in India (about 2,800 posts), and not obviously senior
   and not asking for 2+ years (about 700 posts).
3. **Removes duplicates**: an exact hash of company + title + location, then rapidfuzz ≥ 92%
   on titles from the same company, with Bangalore/Bengaluru-style aliases.
4. **Tags** with Gemini: role (15 fixed categories), city (fixed list), level, confidence.
   The LLM is also a second filter: it drops "Not fresher", "Not a job" and "Not in India".
5. **Publishes** JSON + CSV and redeploys a static site on GitHub Pages. Search and filters
   run in the browser.

Total running cost: **₹0**. That's GitHub Actions, GitHub Pages and the Gemini free tier.

## 2. Numbers (run of 18 Nov 2026, 10:05 IST)

| Step | Posts |
|---|---|
| Fetched | 10,157 |
| Located in India | 2,771 |
| Possible entry-level after rules | 698 |
| Duplicates removed | 99 (82 exact, 17 fuzzy) |
| Rejected by the LLM | 295 |
| **Listed** | **304**: 157 Fresher, 130 Internship, 17 Early career |

### Cost per 1,000 posts
Measured from the token counts the Gemini API reports on every call (`usageMetadata`),
priced at Google's **paid** tier for `gemini-3.1-flash-lite` ($0.25 / 1M input, $1.50 / 1M output):

| | |
|---|---|
| Posts tagged in the last full re-tag (18 Nov, 09:45 IST) | 606 |
| Input tokens / output tokens | 107,359 / 25,920 |
| Cost of the run at paid prices | $0.0657 |
| **Cost per 1,000 posts** | **≈ $0.11 (≈ ₹9)** |
| Tokens per post | ≈ 220 |
| Actual bill (free tier) | $0 |

Why it's cheap: 40 posts per request (the instructions are paid once per 40 posts),
descriptions trimmed to the opening plus the sentences that mention experience, and a
cache, so a post tagged yesterday costs nothing today. Daily cost scales with *new* posts only.

### Tagging accuracy (hand-checked, 50 random posts, seed 42)
| | Correct |
|---|---|
| Role | __ / 50 (__%) |
| City | __ / 50 (__%) |
| Level (intern/fresher/early career) | __ / 50 (__%) |
| Role **and** city both right | __ / 50 (__%) |

Most common mistakes: _fill in from `python eval/score.py`_.

## 3. AI tools used

| Where | Tool |
|---|---|
| Tagging in the product | Google Gemini `gemini-3.1-flash-lite` (REST API, JSON-schema output, temperature 0) |
| Building | Claude Code (pair programming), Claude for reviewing samples |

## 4. The prompt (exact, from `pipeline/tagger.py`)

```
You label Indian job posts for a job board used by college students.

For EACH post, return:
- "i": the post's number, copied exactly.
- "role": the single best category from this list. Judge by what the person will
  actually do day to day, not by buzzwords in the company name:
  ["Software Engineering", "Data & Analytics", "AI / ML", "Product", "Design", "Marketing", "Sales & Business Development", "Operations & Supply Chain", "Finance & Accounting", "HR & Recruiting", "Customer Success & Support", "Content & Communications", "Consulting & Strategy", "Core Engineering", "Other"]
  Notes: "AI / ML" is only for roles that build or research ML models. A data analyst
  or BI role is "Data & Analytics". Business analyst roles are "Consulting & Strategy"
  unless they are mainly SQL/dashboards. QA/test, DevOps, SRE and mobile roles are
  "Software Engineering". Mechanical, electrical, civil, electronics, production,
  maintenance and manufacturing roles (including most "Graduate Engineer Trainee" posts
  at manufacturers) are "Core Engineering", not Software Engineering. Use "Other" only when nothing fits.
- "cities": every Indian city where the job is based, using ONLY these names:
  ["Bengaluru", "Mumbai", "Delhi", "Gurugram", "Noida", "Hyderabad", "Pune", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Kochi", "Chandigarh", "Indore", "Coimbatore", "Thiruvananthapuram", "Remote", "Other India", "Not in India"]
  Map spellings to the list: Bangalore -> Bengaluru, Gurgaon -> Gurugram,
  New Delhi -> Delhi, Bombay -> Mumbai, Trivandrum -> Thiruvananthapuram,
  Cochin -> Kochi. If the job is fully remote in India use "Remote". An Indian city
  that is not in the list is "Other India". If the location field is vague (e.g. just
  "India"), use a city named in the title or description; only if none is named, "Other India". If the job is NOT located in India
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

Return one object per post, in a JSON array. Nothing else.
```

The response is forced into this JSON schema (Gemini structured output), so role, city and
level can only be values from the lists above:

```json
[{"i": 0, "role": "<enum>", "cities": ["<enum>"], "level": "<enum>", "confidence": 0.0}]
```

Each post is sent as:
```
### Post 3
Title: ...
Company: ...
Location: ...
Description start: <first 350 chars>
Experience lines: <every sentence mentioning years / experience / graduate / fresher>
```

## 5. The design choices I'd defend
- **Precision over count.** On the first day the count hit exactly 200, but 153 were
  Bosch jobs wrongly marked "entry level". I threw them out and rebuilt the filters, and I'd
  rather list fewer real fresher jobs than pad the number.
- **Rules first, LLM second.** Regex drops 75% of posts for free; the LLM only sees the unclear ones.
- **Enums plus an escape hatch.** Forced choices stop the model inventing categories, but it
  needs "Not in India" / "Not a job" options or it's forced into a wrong answer (log #15).
- **Labelled levels.** "Early career (up to 2 yrs)" is shown as its own filter instead of
  quietly stretching what "fresher" means.
