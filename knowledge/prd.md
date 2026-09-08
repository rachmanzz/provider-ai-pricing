# Product Requirements Document (PRD)

## Project Name

**AI Catalog Pricing**

## Overview

Build an automated system that collects, tracks, and compares AI provider pricing data on a daily basis, sorted from cheapest to most expensive, **focused only on models usable for coding**. The system runs entirely on GitHub Actions (free tier) and outputs a human-readable `pricing.md` catalog in the repository root.

## Goals

- Scrape pricing data from various AI providers daily
- Filter to **coding-capable models** only (exclude pure image/video/audio models)
- Store pricing history for trend analysis
- Compare prices across providers
- Display results sorted by price (cheapest to most expensive)
- Fully automated — zero manual intervention after initial setup

## Non-Goals

- Real-time pricing updates (daily is sufficient)
- Billing/payment integration
- Provider account management
- Hosting a public website (GitHub repo/README is the output)
- Comparing non-coding models (image/video/audio generation, etc.)

## Tools & Stack

| Tool | Purpose |
|------|---------|
| GitHub Actions | Daily scheduling (cron), CI/CD, auto-commit of results |
| Python | Data scraping, processing, and storage |
| Playwright | Browser automation for scraping JS-rendered pricing pages |
| Third-party OpenAI-compatible API | LLM normalization via `BASE_URL` / `AI_MODEL` / `AI_KEY` secrets |
| Git / GitHub | Version control, history, and artifact hosting |

## Project Structure

```
ai-catalogs/
├── sources.md              # List of provider pricing URLs (canonical source list)
├── pricing.md              # OUTPUT: daily pricing catalog (cheapest at top)
├── knowledge/
│   └── prd.md              # This document
├── scripts/
│   ├── scrape.py           # Playwright scraping of provider pages
│   ├── normalize.py        # LLM-assisted normalization to common schema
│   ├── sort.py             # Sort by price ascending + build pricing.md
│   └── build_report.py     # Generate final pricing.md + history
├── data/
│   ├── raw/                # Raw scraped HTML/text (per date)
│   ├── normalized/         # Normalized JSON (per date)
│   └── history/            # Historical pricing records (append-only)
└── .github/
    └── workflows/
        └── daily-pricing.yml  # Cron job
```

## Features

### 1. Source Management (`sources.md`)

- Canonical list of all provider pricing URLs
- Adding a new provider = adding one row to the table
- Each entry: provider name + official pricing URL

### 2. Daily Price Scraping

- Triggered by GitHub Actions cron (e.g., daily at 00:00 UTC)
- Read URLs from `sources.md`
- Use Playwright to load JS-rendered pricing pages
- Capture pricing tables: model, input price, output price, cached price, unit (per 1M tokens / per image / etc.)
- Save raw output to `data/raw/<date>/`

### 3. Normalization with Third-party LLM API

- Feed raw scraped content to the third-party OpenAI-compatible LLM (`BASE_URL` / `AI_MODEL` / `AI_KEY`)
- **LLM extraction is mandatory — no heuristic fallback**; the run fails loudly if the LLM is unavailable
- Extract and normalize to a common schema:
  - provider, model, modality (text/vision)
  - input_price, output_price, cached_price
  - unit, currency (default USD)
  - scraped_at timestamp
- **Keep only coding-capable models**; drop pure image/video/audio generation models
- **Deduplicate models** — the same model listed by multiple providers appears once (cheapest wins)
- `model` must always be the real model name (never a table header, label, or note)
- Handle inconsistencies (strikethrough discounts, "Free", empty values)
- Save normalized JSON to `data/normalized/<date>/`

### 4. Sorting & Comparison

- Sort all coding models by a canonical price metric (e.g., output price per 1M tokens ascending)
- Cheapest at the top, most expensive at the bottom
- Compare similar capabilities across providers
- Highlight best value options

### 5. Output: `pricing.md` (root)

- Create or update `pricing.md` in the root on every run
- Include full pricing catalog, sorted cheapest → most expensive
- Sections by modality (text, image, video, audio) or a single consolidated table
- Header with scraping date/timestamp

### 6. Data Storage & History

- Store normalized data in `data/normalized/` (per date)
- Append to append-only history in `data/history/`
- Track icon daily snapshots for price-change detection
- `data/raw/` kept for debugging (optionally pruned)

### 7. Reporting & Alerts

- `pricing.md` acts as the daily report
- Price change detection vs previous day
- Optionally create a GitHub issue or comment when a price changes

### 8. Automation & Delivery

- GitHub Actions workflow:
  1. Checkout repo
  2. Setup Python + install dependencies (playwright, etc.)
  3. Run scrape.py
  4. Run normalize.py (with @BASE_URL/AI_MODEL/AI_KEY if available, else heuristics)
  5. Run sort.py + build_report.py → write pricing.md
  6. Commit + push updated pricing.md and data/
  7. (Optional) Create issue on price change

## Target Providers (from `sources.md`)

- Z.AI (GLM)
- Cheaper Inference
- Together AI
- OpenAI
- Anthropic
- Google (Gemini)
- Mistral
- Cohere
- DeepSeek
- Replicate
- Groq
- Fireworks AI
- OpenRouter
- Hugging Face

## Data Schema (Normalized)

```json
{
  "provider": "z.ai",
  "model": "GLM-5.3-Flash",
  "modality": "text",
  "input_price": 0.075,
  "output_price": 0.25,
  "cached_input_price": 0.015,
  "unit": "per_1M_tokens",
  "currency": "USD",
  "notes": "50% discount until 2026-09-09",
  "scraped_at": "2026-09-08T00:00:00Z"
}
```

## Success Criteria

- Daily automated runs via GitHub Actions
- Accurate pricing data for all tracked providers
- `pricing.md` generated each day **only with coding-capable models**, sorted (cheapest → most expensive)
- Historical data retained for trend analysis
- Adding a provider is a one-line edit to `sources.md`

## Implementation Phases

### Phase 1 — MVP (scrape + output)
- Set up GitHub Actions cron
- Scrape `sources.md` URLs via Playwright
- Filter + extract coding models + write `pricing.md` sorted by price

### Phase 2 — LLM Normalization
- Integrate third-party OpenAI-compatible LLM for robust extraction
- Handle messy tables, discounts, and varying units
- Keep only coding-capable models
- Store normalized JSON

### Phase 3 — History & Alerts
- Append-only history store
- Price-change detection and GitHub issue alerts
- Trend analysis

## Out of Scope

- Real-time pricing updates
- Billing/payment integration
- Provider account management
- Public web dashboard (repo README/pricing.md suffices)
