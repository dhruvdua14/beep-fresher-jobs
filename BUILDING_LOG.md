# Building log: what broke and how I fixed it

A running list, newest at the bottom. Each entry: what happened, why, the fix.

---

### 1. My dev machine couldn't reach a single job API
**What happened:** The first test fetch from the cloud dev box returned `403` from
the network proxy for Greenhouse, Lever, Ashby and Adzuna.
**Why:** The sandbox only allows a short list of hosts.
**Fix:** Stopped treating "my machine" as the place the pipeline runs. GitHub Actions
is where it runs every day anyway, so I test fetching there with the "Run workflow"
button. Dev and production are now the same environment, which removed a whole class
of "works on my machine" bugs. Same reason I host on GitHub Pages instead of Vercel:
one repo, one place to look when something breaks.

### 2. Dedupe missed obvious duplicates
**What happened:** Test data with the same internship listed as
`Software Engineer Intern / Bangalore, India` (company API) and
`Software Engineer Intern / Bengaluru, Karnataka, India` (Adzuna) came out as 2 posts.
So did `Software Engineer Intern` vs `Software Engineer Intern (2026)`.
**Why:** The fuzzy pass required locations to share a word, and "Bangalore" ≠
"Bengaluru". The year made titles only ~90% similar, under my 92% threshold.
**Fix:** Map old city names to new ones before comparing locations, and strip
years/"batch"/"summer" from titles before the similarity check. Didn't lower the
threshold, because that started merging genuinely different roles
(e.g. "Backend Intern" vs "Frontend Intern").

_Caught while writing tests for the filter rules, before anything shipped:_

### 3. The "senior" rule threw away Associate Product Manager roles
**What happened:** APM is the classic campus PM role, but the title contains
"Manager", which my senior-title regex drops.
**Fix:** Intern-type titles are checked first and win. APM is now in that list.

### 4. "India" matched "Indiana"
**What could happen:** A plain substring check would treat `Indianapolis, Indiana` as India.
**Fix:** Word boundaries in the regex (`\bindia\b`). Tested with Indiana explicitly.

### 5. Day one: every single post was marked "New"
**What happened:** "New" means "first seen today". On the first run, everything is
first seen today, so the badge carried no information.
**Fix:** The page only shows "New" once some posts have an earlier first-seen date.

### 6. A hidden button wasn't hidden
**What happened:** "Clear filters" showed up even with no filters active.
**Why:** I reset button styles with `all: unset`, which also wipes the browser's
`display: none` for the `hidden` attribute.
**Fix:** One CSS rule: `[hidden] { display: none !important; }`.

### 7. The aggregator API wanted a credit card
**What happened:** I planned Adzuna's India API as the high-volume source. After
signing up, full access needed a card on file. The free tier was 25 test calls.
**Fix:** Made Adzuna optional (it only runs if its keys are set, and on the 25-call test plan it spends at most 2 calls a run) and added two more
free, keyless careers-page APIs instead: Workable and Recruitee. Volume now comes
from many company boards rather than one aggregator. Bonus: every link goes straight
to the employer, and there's less cross-site duplication.

### 8. First live run: 8,194 posts fetched, only 49 listed, and zero tagged
Two separate failures in the very first run on GitHub Actions.

**(a) The model name didn't exist any more.** Every Gemini call returned `404`.
I'd hard-coded `gemini-2.5-flash-lite`, and Google retires model names.
**Fix, take 1:** Ask the API which models this key can use and pick the first from a
preference list. Second run: the API *listed* `gemini-2.5-flash-lite`... and still
answered 404 on every call. Listed ≠ usable (it's retired for new keys).
**Fix, take 2:** On a 404 the tagger moves to the next model in the list and retries
the same batch. Now on `gemini-3.1-flash-lite`. Prices are kept per model in
`config.PRICES`, so the cost figure always matches the model that actually ran.

**(b) The rules were too strict.** 1,750 posts were in India, but only 50 passed the
fresher regex. Most Indian job posts for freshers don't say "fresher" in the title.
They're just "Software Engineer" or "Business Analyst", with "0–1 years" buried in the
requirements, which sat beyond the first 1,500 characters I was keeping.
**Fix:** (1) Keep 8,000 characters of description so the requirements section is
there. (2) Rules now only *drop* the clear cases: senior titles, or 2+ years required.
Anything unclear goes to the LLM, which gets the description opening plus every
sentence mentioning years, experience or graduation, and decides the level. The
prompt tells it "when unsure, say Not fresher", because a student wasting time on a
job they can't get is worse than missing one. (3) 40 posts per call instead of 20, to
stay inside the free tier's daily request limit.

Also: GitHub Pages wasn't switched on yet, so the deploy step failed with `Not Found`.

### 9. The bot's data commit collided with my code commit
**What happened:** I pushed a code fix while a run was in progress. When the run
finished, its `git push` of the new data was rejected (non-fast-forward), because
`main` had moved on.
**Fix:** The workflow now does `git pull --rebase` right before pushing. Data files and
code files never overlap, so the rebase is always clean.

### 10. 200 posts, but 153 of them were from Bosch, and many weren't fresher jobs
**What happened:** The run reached exactly 200 listings, but the list was suspicious:
one company had 153 of them, including "System Project Leader" and "Team Leader Production".
**Why:** SmartRecruiters' list API has no job description. I'd been passing its
`experienceLevel` field instead, and Bosch marks nearly every job "entry_level". The LLM
trusted that hint because it had nothing else to go on. My senior-title regex had
`lead` but not `leader` or `specialist`.
**Fix:** (1) Stop trusting `entry_level`; only "internship" counts as a hint. (2) Fetch the
real description per post, but only for India posts that survive the title rules
(a few hundred calls, not thousands). (3) Add `leader` and `specialist` to the senior
regex. (4) A `PROMPT_VERSION` on cached tags, so changing the prompt or its inputs
re-tags everything instead of keeping stale answers.
**Lesson for the hand check:** the count looked fine, and only reading the rows showed
it was wrong. That's why the 50-post eval matters.

### 11. Adzuna said 401 even with the right key
**What happened:** The request URL had `app_id=…%0A%0A`: the secret had been pasted
with two trailing newlines.
**Fix:** `.strip()` every key read from the environment.

### 12. After fixing precision, only 88–125 real 0–1 year posts were left
**What happened:** With honest tagging, Bosch dropped from 153 to 0 and the total fell
below 200. Most of the rest came from Adzuna, whose free plan only allows 25 calls in total.
**What I tried:** The Muse's public API, which filters by Indian city and "Entry Level".
It returned `403` from GitHub's servers (it blocks datacenter IPs), so I removed it again.
**What I did instead:**
1. **Added a third level, "Early career (up to 2 yrs)", next to Internship and Fresher.**
   The LLM was throwing away posts asking for "1–2 years", which a strong final-year
   student can still apply to. Rather than quietly stretching the meaning of "fresher",
   the site labels it and lets students filter it out. The experience regex was rewritten
   too: it reads the *minimum* years asked ("1–2 years" means 1, "2+ years" means 2) and only
   counts numbers next to "experience", so "founded 25 years ago" no longer counts.
2. **Adzuna archive:** each post Adzuna returns is kept and listed until it's 30 days
   old, so 2 calls a day add up instead of being thrown away. The queries rotate daily.

I chose fewer, honest, clearly labelled listings over padding the count with mislabelled ones.

### 13. "Early career" let the junk back in
**What happened:** Reading 30 random rows after adding Early career, I found "Intermediate
Backend Engineer", "Workload Automation Consultant", a "Talent Community" page, a
"Test Employee" placeholder, and spammy "data entry on your Android phone" ads from an aggregator.
**Fix:** (1) Early career now needs a *stated* requirement of 2 years or less. Silence about
experience means Not fresher. (2) A fifth level, "Not a job", for talent pools, general
applications, test posts and pay-to-join schemes. (3) A cheap title regex catches the
obvious ones before they cost tokens. (4) An optional Jooble source (free key, no card)
for volume.

### 14. Jooble returned 119 posts and only 8 survived
**What happened:** Each Jooble search stopped after one short page. Its snippets are
2 lines long, so the LLM saw no experience requirement and, following my "silence =
Not fresher" rule, rejected them, even though Jooble had found them by searching "fresher".
**Fix:** (1) Search per city (14 cities × 3 queries × 2 pages of 50), since a single
India-wide search is dominated by Bengaluru. (2) Tell the LLM which search matched
the post ("Matched the job-board search 'fresher'"). That's real evidence, and the prompt
now says it counts unless the post asks for more experience.
