# AI tools and prompts used

## In the product

| Where | Tool | Why this one |
|---|---|---|
| Role / city / level tagging | Google Gemini `gemini-2.5-flash-lite` via REST API | Free tier is enough for a daily run, supports JSON-schema output with enums, cheapest paid price if it ever scales |

The exact prompt lives in [`pipeline/tagger.py`](../pipeline/tagger.py) (`PROMPT`), and the
JSON schema the model is forced to follow is `SCHEMA` in the same file. Settings:
`temperature = 0`, 20 posts per request, description cut to 600 characters.

Each post is sent like this:

```
### Post 3
Title: Data Analyst Intern
Company: Groww
Location: Bengaluru, Karnataka, India
Description: <first 600 characters>
```

and the model must return, for every post:

```json
{"i": 3, "role": "Data & Analytics", "cities": ["Bengaluru"], "level": "Internship", "confidence": 0.95}
```

### Prompt design decisions
- **Fixed lists, enforced by schema.** The model can't invent "SDE" as a role or
  "Bangalore Urban" as a city: the API rejects anything outside the enum.
- **Tie-break rules in the prompt** for the confusions I expect (data analyst vs AI/ML,
  QA/DevOps → Software Engineering, business analyst). These come from the hand check.
- **Level as a second filter.** Regex rules are cheap but crude; the model catches
  "Junior X, 3+ years" style posts and they're dropped.
- **Batching 20 posts** so the ~600-token instructions are paid once per 20 posts.

## While building
- Claude Code: pair-programming the pipeline, the site and this documentation.
