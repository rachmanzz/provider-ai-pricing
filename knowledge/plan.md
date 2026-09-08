# Implementation Plan

Comprehensive execution blueprint for the AI Catalog Pricing project. Follow phases in order.

## Phase 1 — Project Setup & Foundations

### 1.1 Initialize Repo Structure

```
ai-catalogs/
├── sources.md
├── pricing.md              # output
├── knowledge/
│   ├── prd.md
│   └── plan.md             # this file
├── scripts/
│   ├── scrape.py
│   ├── normalize.py
│   ├── sort.py
│   └── build_report.py
├── data/
│   ├── raw/
│   ├── normalized/
│   └── history/
└── .github/workflows/
    └── daily-pricing.yml
```

**Checklist**
- [ ] Create `scripts/` and `data/` directories
- [ ] Add empty `.gitkeep` files to keep empty dirs tracked
- [ ] Create empty placeholder `pricing.md` with `# AI Catalog Pricing`

### 1.2 Dependency Setup

Create `requirements.txt`:

```
playwright
beautifulsoup4
lxml
pandas
```

**Checklist**
- [ ] `pip install -r requirements.txt`
- [ ] `playwright install chromium`

---

## Phase 2 — Scraping

### 2.1 `scripts/scrape.py`

- Read URLs from `sources.md` (parse markdown table)
- Use Playwright to load each page (headless Chromium)
- Wait for content / network idle
- Capture the rendered HTML and visible text
- Save to `data/raw/<YYYY-MM-DD>/<provider>.html` and `.txt`

**CLI**
```
python scripts/scrape.py --date 2026-09-08
python scripts/scrape.py                # uses today
```

**Checklist**
- [ ] Parse `sources.md` markdown table correctly
- [ ] Handle pages that need JS rendering
- [ ] Timeout + retry logic per provider
- [ ] Write raw output to `data/raw/<date>/`
- [ ] Log success/failure per provider

---

## Phase 3 — Normalization

### 3.1 `scripts/normalize.py`

- Read raw `.txt` from `data/raw/<date>/`
- Extract models + prices into the normalized schema:

```json
{
  "provider": "...",
  "model": "...",
  "modality": "text",
  "input_price": 0.0,
  "output_price": 0.0,
  "cached_input_price": null,
  "unit": "per_1M_tokens",
  "currency": "USD",
  "notes": "...",
  "scraped_at": "2026-09-08T00:00:00Z"
}
```

- LLM (third-party OpenAI-compatible API) extraction is **mandatory** — no heuristic fallback
- Keep **coding models only**; exclude image/video/audio/embeddings
- **Dedupe models** — the same model listed by multiple providers appears only once (cheapest wins)
- Handle: "Free", strikethrough discounts, missing values, $ symbols

**CLI**
```
python scripts/normalize.py --date 2026-09-08
```

**Checklist**
- [ ] Fails loudly if `BASE_URL`/`AI_MODEL` unset (no silent garbage output)
- [ ] `model` field is always a real model name (never a table header/note)
- [ ] Consistent schema for all providers
- [ ] Correctly parse numbers from `$0.075`, `Free`, `-`
- [ ] No duplicate models in output
- [ ] Merge all providers into one normalized JSON file
- [ ] Save to `data/normalized/<date>/all.json`
- [ ] Abort (non-zero exit) if zero records extracted

---

## Phase 4 — Sorting & Report Generation

### 4.1 `scripts/sort.py`

- Load `data/normalized/<date>/all.json`
- Sort ascending by canonical price metric (output price per 1M tokens by default)
- Cheapest first, most expensive last

### 4.2 `scripts/build_report.py`

- Generate markdown table(s) from sorted data
- Sections by modality, or one consolidated table
- Header with date + timestamp
- Write to root `pricing.md`

**Example output structure:**

```markdown
# AI Catalog Pricing
_Generated: 2026-09-08 00:00 UTC_

## Text Models (sorted by output price, asc)

| Rank | Provider | Model | Input | Output | Cached | Unit |
|------|----------|-------|-------|--------|--------|------|
| 1    | z.ai     | GLM-4.7-Flash | Free | Free | Free | /1M tok |
| ...  |          |       |       |        |        |      |
```

**Checklist**
- [ ] Sort order correct (cheapest → most expensive)
- [ ] Valid markdown table rendering
- [ ] Handles duplicate model names across providers
- [ ] Writes cleanly to `pricing.md`

---

## Phase 5 — History & Change Detection

### 5.1 `data/history/`

- Append each daily normalized snapshot to `data/history/`
- One JSON file per date or append to a single `history.jsonl`

### 5.2 Price Change Detection

- Compare today's snapshot with yesterday's
- Flag models where output/input price changed
- Output a `changes.json` (list of {model, before, after})

**Checklist**
- [ ] Append-only history (never mutate past records)
- [ ] Reliable diff between consecutive days
- [ ] Change detection handles removed/new models

---

## Phase 6 — GitHub Actions Automation

### 6.1 `.github/workflows/daily-pricing.yml`

```yaml
name: Daily Pricing

on:
  schedule:
    - cron: '0 0 * * *'   # daily at 00:00 UTC
  workflow_dispatch:      # manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install deps
        run: |
          pip install -r requirements.txt
          playwright install chromium --with-deps
      - name: Scrape
        run: python scripts/scrape.py
      - name: Normalize
        run: python scripts/normalize.py
      - name: Build report
        run: python scripts/build_report.py
      - name: Commit & push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "chore: update pricing $(date +%F)" || echo "no changes"
          git push
```

**Checklist**
- [ ] Cron schedule correct (UTC)
- [ ] Playwright dependencies installed in CI
- [ ] Auto-commit/push works without failing on "no changes"
- [ ] LLM secrets (`BASE_URL`, `AI_MODEL`, `AI_KEY`) passed via `env:` in the workflow

---

## Phase 7 — LLM Normalization (Third-party API)

### 7.1 Integrate OpenAI-compatible LLM API

- Pass raw text batches to an OpenAI-compatible third-party API
- Prompt: "Extract models & prices into JSON" with schema example
- Credentials come from GitHub secrets:
  - `BASE_URL` → OpenAI-compatible base URL (e.g. `https://api.example.com/v1`)
  - `AI_MODEL` → model id (e.g. `big-pickle` or provider model)
  - `AI_KEY` → API key
- Fall back to heuristic extraction if API unavailable/rate-limited

**Example call (OpenAI-compatible endpoint):**

```python
import requests

resp = requests.post(
    f"{BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"},
    json={
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": "Extract model pricing into JSON."},
            {"role": "user", "content": raw_text},
        ],
    },
)
```

**Checklist**
- [ ] Read `BASE_URL`, `AI_MODEL`, `AI_KEY` from env (undefined BASE_URL → skip LLM)
- [ ] Robust prompt with few-shot examples
- [ ] Retry/timeout handling for API calls
- [ ] Graceful fallback to heuristic extraction
- [ ] Cache results to avoid re-hitting API on retries

---

## Phase 8 — Alerts (Optional)

### 8.1 Price-Change Issues

- After building report + detecting changes
- Create a GitHub issue summarizing price changes
- Uses `gh` CLI or GitHub API (with `GH_TOKEN` secret)

**Checklist**
- [ ] Creates issue only when changes detected
- [ ] Issue lists affected models with before/after prices
- [ ] Dedupes (no duplicate issues for same change)

---

## Phase 9 — Final Integration & Testing

### 9.1 Dry Run Locally

```bash
python scripts/scrape.py --date $(date +%F)
python scripts/normalize.py --date $(date +%F)
python scripts/build_report.py --date $(date +%F)
```

### 9.2 Verify Outputs

- [ ] `data/raw/` has files per provider
- [ ] `data/normalized/<date>/all.json` valid + complete
- [ ] `pricing.md` generated and sorted (cheapest at top)
- [ ] `data/history/` updated
- [ ] No secrets leaked into committed files

### 9.3 Push & Trigger

- [ ] Commit all files
- [ ] Run workflow manually (`workflow_dispatch`)
- [ ] Confirm scheduled run the next day

---

## Milestone Summary

| Phase | Description | Done |
|-------|-------------|------|
| 1 | Project setup & dependencies | ☐ |
| 2 | Scraping (`scrape.py`) | ☐ |
| 3 | Normalization (`normalize.py`) | ☐ |
| 4 | Sorting + report (`sort.py`, `build_report.py`) | ☐ |
| 5 | History & change detection | ☐ |
| 6 | GitHub Actions automation | ☐ |
| 7 | LLM normalization (third-party API) | ☐ |
| 8 | Alerts (optional) | ☐ |
| 9 | Final integration & testing | ☐ |
