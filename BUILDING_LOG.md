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
