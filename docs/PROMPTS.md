# AI tools and prompts used

## In the product

| Where | Tool | Why this one |
|---|---|---|
| Role / city / level tagging | Google Gemini `gemini-3.1-flash-lite` via REST API (picked automatically from a preference list) | Free tier is enough for a daily run, supports JSON-schema output with enums, cheapest paid price if it ever scales |

The exact prompt lives in [`pipeline/tagger.py`](../pipeline/tagger.py) (`PROMPT`), and the
JSON schema the model is forced to follow is `SCHEMA` in the same file. Settings:
`temperature = 0`, 40 posts per request; each post sends the first 350 characters of the description plus every sentence that mentions experience or graduation.

Each post is sent like this:

```
### Post 3
Title: Data Analyst Intern
Company: Groww
Location: Bengaluru, Karnataka, India
Description start: <first 350 characters>
Experience lines: <sentences mentioning years / experience / graduate / fresher>
```

and the model must return, for every post:

```json
{"i": 3, "role": "Data & Analytics", "cities": ["Bengaluru"], "level": "Internship", "confidence": 0.95}
```

`level` is one of Internship, Fresher, Early career, Not fresher, Not a job. Only the first
three are listed. `cities` may be "Not in India", and those posts are dropped.

### Prompt design decisions
- **Fixed lists, enforced by schema.** The model can't invent "SDE" as a role or
  "Bangalore Urban" as a city: the API rejects anything outside the enum.
- **Tie-break rules in the prompt** for the confusions I expect (data analyst vs AI/ML,
  QA/DevOps → Software Engineering, business analyst). These come from the hand check.
- **Level as a second filter.** Regex rules are cheap but crude; the model catches
  "Junior X, 3+ years" style posts and they're dropped.
- **Batching 40 posts** so the ~600-token instructions are paid once per 40 posts.

## While building
- Claude Code: pair-programming the pipeline, the site and this documentation.
