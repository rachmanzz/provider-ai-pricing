# AI Catalog Pricing

Daily automated comparison of **coding-capable AI model prices** across providers, sorted from **cheapest to most expensive**.

## Overview

This repository scrapes AI provider pricing pages every day and generates a sorted catalog (`pricing.md`) so you can quickly find the cheapest model for coding. The pipeline runs entirely on GitHub Actions and commits results automatically.

## Features

- **Daily scraping** of 14+ AI provider pricing pages via Playwright
- **Coding models only** — filters out image/video/audio generation, embeddings, TTS
- **LLM-assisted extraction** via a third-party OpenAI-compatible API
- **Sorted by price** — cheapest first, most expensive last
- **Change detection** — flags price changes vs. the previous day
- **Full history** — per-day snapshots stored in `data/history/`

## Output

The generated catalog lives at [pricing.md](pricing.md), produced daily:

```
# AI Catalog Pricing

| Rank | Provider | Model | Input | Output | Cached | Unit | Notes |
|------|----------|-------|-------|--------|--------|------|-------|
| 1    | ...      | ...   | ...   | ...    | ...    | ...  | ...   |
```

## Project Structure

```
ai-catalogs/
├── sources.md              # Provider pricing URLs (edit to add providers)
├── pricing.md              # OUTPUT: daily sorted catalog (cheapest at top)
├── knowledge/
│   ├── prd.md              # Product requirements
│   └── plan.md             # Implementation plan
├── scripts/
│   ├── scrape.py           # Playwright scraping → data/raw/
│   ├── normalize.py        # LLM/heuristic extraction → data/normalized/
│   └── build_report.py     # Sort + build pricing.md + change detection
├── data/
│   ├── raw/                # Raw HTML/text scrapes (gitignored)
│   ├── normalized/         # Normalized JSON per date
│   └── history/            # Daily snapshots (append-only)
└── .github/workflows/
    └── daily-pricing.yml   # Cron job (00:00 UTC)
```

## Setup

### 1. Repository Secrets

Configure these secrets (Settings → Secrets and Variables → Actions) for high-quality LLM extraction:

| Secret      | Description                                            |
|-------------|--------------------------------------------------------|
| `BASE_URL`  | OpenAI-compatible API base URL (e.g. `https://api.example.com/v1`) |
| `AI_MODEL`  | Model id to use for extraction                         |
| `AI_KEY`    | API key                                               |

> Without secrets, the pipeline falls back to heuristic extraction (lower accuracy).

### 2. Workflow Permissions

Set **Actions → General → Workflow permissions → Read and write permissions** so the workflow can auto-commit results.

### 3. Manual First Run

Trigger the workflow once:

```
Actions → Daily Pricing → Run workflow
```

After that it runs automatically every day at 00:00 UTC.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

python scripts/scrape.py            # scrape today
python scripts/normalize.py         # extract (LLM or heuristic)
python scripts/build_report.py      # build pricing.md
```

## Adding a Provider

Add one row to `sources.md`:

```markdown
| My Provider | https://my-provider.com/pricing |
```

## License

MIT