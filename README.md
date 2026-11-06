# AI Job Search Agent

Upload your CV, pick a role, and get live job listings ranked by how well
your skills match each one — with skill gaps, a human-in-the-loop approval
step, and AI-generated tailored application materials.

**Stack:** FastAPI · LangGraph (Postgres checkpoints) · Groq LLM · Adzuna API · React + Vite

## Job sources

Every search automatically queries **all sources** and merges the results (duplicates removed). A source that fails or has no key is skipped, so the app works with just Adzuna keys. (API users can still pass `source=adzuna|remotive|jooble` to the search endpoint to use one.)

| Source | Coverage | Key needed | Notes |
|--------|----------|-----------|-------|
| Adzuna | 17 countries (gb, us, au, at, br, ca, de, es, fr, in, it, mx, nl, nz, pl, sg, za) | Yes (free) | Short previews; the app tries to fetch the full text |
| Remotive | Remote jobs only, mostly tech | No | Returns full descriptions (best matching accuracy). Listings are delayed ~24h; results are cached 6h; each job is credited and linked to Remotive as their terms require. For this source, the *Location* box means "where can I work from" - e.g. `Pakistan` keeps worldwide jobs plus Pakistan/Asia-specific ones |
| Jooble | 60+ countries | Yes (free, by request at jooble.org/api/about) | Short snippets. Type a city or country in *Location* |
| All sources | Everything available | - | Merges results, removes duplicates, and skips any source that fails or has no key |

Respect each provider's terms: this tool is intended for personal use.
Do not republish Remotive listings on other job sites.

## How matching works

| Step | What happens |
|------|--------------|
| 1. CV | PDF text is extracted; skills are read by the LLM (temperature 0) **and** by a deterministic taxonomy scan, so nothing written on your CV is missed. |
| 2. Search | Adzuna returns listings (short previews only). |
| 3. Enrich | The full listing text is fetched when the page exposes it (schema.org `JobPosting` or a description block). Otherwise the preview is used and clearly labelled. |
| 4. Extract | Required / preferred skills come from a **deterministic** taxonomy pass. The LLM may add extra skills only if they literally appear in the text. Results are cached, so the same job always gives the same answer. |
| 5. Score | `(direct matches + 0.5 × related matches) / required skills`. |
| 6. Rank | Ordered by a confidence-adjusted score so "1 of 1 skills" can't outrank "8 of 10". |

### Reading a result

* **Confidence** — *High*: 5+ skills from the full listing. *Medium*: 3–4 skills, or a short preview. *Low*: fewer than 3 skills; the percentage is shown dashed with a warning.
* **Insufficient data** — shown only when *no* technical skills can be read from the listing.
* **Partly covered** — you list related tools (e.g. PyTorch for "machine learning"); worth half credit.
* The score measures **skill overlap**, not overall suitability.

## Setup

```bash
# 1. Backend
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # then fill in your keys   (macOS/Linux: cp)

# 2. Frontend
cd frontend
npm install
```

You need a PostgreSQL database (any free tier such as Neon or Supabase works)
and API keys for [Adzuna](https://developer.adzuna.com/) and [Groq](https://console.groq.com/).

## Run

```bash
# terminal 1 — API (from the project root)
uvicorn backend.api:app --reload

# terminal 2 — UI
cd frontend && npm run dev          # http://localhost:5173
```

No database yet? Try the pipeline from the terminal:

```bash
python -m backend.dev_scripts.run_search path/to/cv.pdf "ai engineer" London
python -m backend.dev_scripts.run_search cv.pdf "python developer" "New York" us
```

## Tests (offline, no API keys needed)

```bash
pytest
```

Covers the reported bugs directly: the same job always yields the same
result, one-skill listings are never shown as a confident 100%, and
unscored jobs rank last.

## Configuration

See `.env.example`. Useful switches: `ENRICH_DESCRIPTIONS=false` to skip
fetching full listings, `USE_LLM_JOB_ANALYSIS=false` to run fully
deterministically, `ADZUNA_COUNTRY` for the default market.

Adzuna does not cover Pakistan. From Pakistan, use **Remotive** (remote jobs
open to your region) or **Jooble** with location `Pakistan`/`Karachi`
(check that Jooble returns results for your location).

## Project layout

```
backend/
  api.py                  FastAPI endpoints
  workflows/              LangGraph pipelines (search → rank → review → apply)
  tools/
    skill_taxonomy.py     deterministic skill vocabulary + matching
    job_enricher.py       full-listing text retrieval
    job_analyzer.py       requirement extraction (deterministic + grounded LLM)
    job_matcher.py        scoring, related-skill credit, confidence
    job_ranking.py        confidence-adjusted ranking, skill gaps
    job_sources.py        Adzuna / Remotive / Jooble adapters + "all sources" merge
    cv_analyzer.py / cv_parser.py / job_search.py / job_filters.py
    application_generator.py
  tests/                  offline regression + integration tests
  dev_scripts/            CLI runner and the original live stage scripts
frontend/                 React UI
```

## Known limits

* Full-listing retrieval is best-effort: some job boards block automated
  requests. Those jobs fall back to the preview and show *Short preview only*.
* The taxonomy covers common software, data, AI and cloud skills. Add terms
  in `backend/tools/skill_taxonomy.py`; unknown skills can still be picked up
  by the LLM supplement when it is enabled.
