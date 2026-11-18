# Fresher Ledger

**Live:** https://dhruvdua14.github.io/beep-fresher-jobs/  ·  **Numbers:** [/stats.html](https://dhruvdua14.github.io/beep-fresher-jobs/stats.html)

A job board of internships and fresher jobs in India that rebuilds itself every
morning. It pulls posts from public job-board APIs, keeps entry-level roles in
India, removes duplicates, uses an LLM to tag each post by role and city, and
publishes a searchable static site.

Everything is free: GitHub Actions (cron + compute), GitHub Pages (hosting),
Gemini free tier (LLM).

## Architecture

```
 GitHub Actions, every day 08:00 IST
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ pipeline/run.py                                                          │
 │                                                                          │
 │  sources.py ──► filters.py ──► dedupe.py ──► tagger.py ──► site/data/*.json
 │  Greenhouse     India?         exact hash    Gemini, 20     jobs.json     │
 │  Lever          entry-level?   + rapidfuzz   posts/call,    stats.json    │
 │  Ashby          (regex, free)                JSON schema,   jobs.csv      │
 │  SmartRecruiters                             cached by id                 │
 │  Workable, Recruitee                                                      │
 │  (Adzuna: optional)                                                       │
 └───────────────┬──────────────────────────────────────────────────────────┘
                 │ git commit data/ + site/data/
                 ▼
         GitHub Pages ──► site/index.html  (search + filters, all in the browser)
                          site/stats.html  (funnel, cost, accuracy, run log)
```

| File | What it does |
|---|---|
| `pipeline/config.py` | **Start here.** Company list, role list, city list, model, prices |
| `pipeline/sources.py` | One fetch function per platform, all returning the same shape |
| `pipeline/filters.py` | Regex rules: is it in India, is it entry-level |
| `pipeline/dedupe.py` | Exact + fuzzy duplicate removal |
| `pipeline/tagger.py` | The LLM prompt, JSON schema, batching, caching, token counting |
| `pipeline/run.py` | Runs the steps in order and writes the output files |
| `data/` | The pipeline's memory: tag cache, first-seen dates, run history |
| `site/` | The website. Plain HTML/CSS/JS, no build step |
| `eval/` | 50-post hand check: `sample.py` makes the sheet, `score.py` scores it |
| `.github/workflows/daily.yml` | The cron job and the deploy |

## Why it's built this way
- **Public APIs only, no keys, no payment.** Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Recruitee publish these
  endpoints so other sites can list a company's jobs. No HTML scraping, and no
  LinkedIn/Naukri/Internshala, whose terms forbid it.
- **Rules before the LLM.** Of thousands of fetched posts, most are senior or abroad.
  A regex drops them for free; the LLM only sees the few hundred that might matter.
- **LLM as tagger *and* second filter.** It returns a `level`; anything marked
  "Not fresher" is dropped.
- **Cache by post id.** A post tagged yesterday costs nothing today, so daily cost
  scales with *new* posts, not total posts.
- **Static site.** Search runs in the browser on a ~100 KB JSON file. Nothing to keep alive.

## Common changes (and where to make them)

| I want to… | Change |
|---|---|
| Add a company | Add its slug to `GREENHOUSE` / `LEVER` / `ASHBY` / `SMARTRECRUITERS` / `WORKABLE` / `RECRUITEE` in `config.py` |
| Add a role category or a city | Add it to `ROLES` / `CITIES` in `config.py`, then delete `data/tag_cache.json` to re-tag |
| Change the prompt | `PROMPT` in `tagger.py` |
| Use a different model | `GEMINI_MODELS` (preference order) + its price in `PRICES`, in `config.py` |
| Change the refresh time | `cron` in `.github/workflows/daily.yml` (it's in UTC) |
| Make the fresher filter stricter/looser | Regexes in `filters.py` |
| Refresh right now | Actions tab → Daily refresh → Run workflow |

## Run it locally

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...            # free at aistudio.google.com/apikey
python pipeline/run.py               # writes site/data/
python -m http.server -d site 8000   # open http://localhost:8000
```

## Accuracy and cost
See the [Numbers page](https://dhruvdua14.github.io/beep-fresher-jobs/stats.html).
Hand-check method: `python eval/sample.py` picks 50 posts with a fixed seed into
`eval/hand_check.csv`; each is checked against the original listing and marked Y/N;
`python eval/score.py` computes accuracy and the confusion list. Cost per 1,000 posts =
the API's reported input/output tokens × Gemini's paid-tier price ÷ posts tagged.

Prompts and AI tools: [docs/PROMPTS.md](docs/PROMPTS.md). What broke: [BUILDING_LOG.md](BUILDING_LOG.md).
