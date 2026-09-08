#!/usr/bin/env python3
"""Normalize scraped pricing text into a common JSON schema.

Uses an OpenAI-compatible LLM (BASE_URL / AI_MODEL / AI_KEY env vars) for
robust extraction, falling back to regex/heuristic parsing when no valid LLM
response is available.

Usage:
    python scripts/normalize.py --date 2026-09-08
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
NORM_DIR = ROOT / "data" / "normalized"
HIST_DIR = ROOT / "data" / "history"

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
AI_MODEL = os.environ.get("AI_MODEL", "big-pickle").strip()
AI_KEY = os.environ.get("AI_KEY", "").strip()

SYSTEM_PROMPT = """You are a pricing-data extractor focused on CODING models.
Extract AI model pricing into JSON. KEEP ONLY models usable for CODING/LLM
text generation (chat/code models). EXCLUDE pure image/video/audio generation
models, embeddings, TTS, rerankers, and non-coding tools.
Return ONLY valid JSON, an array of objects with this exact schema:
{"provider": str, "model": str, "modality": "text|vision",
 "input_price": number|null, "output_price": number|null,
 "cached_input_price": number|null, "unit": "per_1M_tokens",
 "currency": "USD", "notes": str, "scraped_at": str}
Prices are per 1M tokens unless the page says otherwise. "Free" = 0. Empty/missing = null.
Handle strikethrough discounts as current price. Example:
[{"provider":"z.ai","model":"GLM-5.3-Flash","modality":"text","input_price":0.075,
"output_price":0.25,"cached_input_price":0.015,"unit":"per_1M_tokens","currency":"USD",
"notes":"50% discount","scraped_at":"2026-09-08T00:00:00Z"}]"""

SCHEMA_FIELDS = ["provider", "model", "modality", "input_price", "output_price",
                 "cached_input_price", "unit", "currency", "notes", "scraped_at"]

PRICE_RE = re.compile(r"[^\d.]")


def llm_extract(provider, text):
    """Use OpenAI-compatible LLM endpoint. Returns list of dicts or None."""
    if not BASE_URL:
        return None
    # provider name known from sources.md, inject into prompt context
    user = f"Provider: {provider}\n\nScraped page text:\n{text[:12000]}"
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    if AI_KEY:
        headers["Authorization"] = f"Bearer {AI_KEY}"
    try:
        r = requests.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return parse_llm_json(content, provider)
    except Exception as exc:
        print(f"  [llm] error for {provider}: {exc}")
        return None


def parse_llm_json(content, provider):
    """Robustly extract a JSON array from an LLM response."""
    m = re.search(r"\[.*\]", content, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        row["provider"] = provider
        for f in SCHEMA_FIELDS:
            row.setdefault(f, None if f != "currency" else "USD")
        out.append(row)
    return out


def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    s = str(v).strip().lower()
    if s in ("", "-", "n/a", "na", "--", "\u2014", "\u2013"):
        return None
    if "free" in s:
        return 0.0
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums:
        return None
    return round(float(nums[0]), 6)


EXCLUDE_TERMS = [
    "image", "video", "audio", "tts", "vocal", "speech", "asr", "transcrib",
    "embed", "rerank", "moderat", "flux", "dall-e", "sora", "veo", "cogvideo",
    "cogview", "seedream", "seedance", "kling", "wan ", "imagen", "nano banana",
    "gpt-image", "glm-ocr", "reranker",
]


def is_coding_model(rec):
    """Heuristic filter: keep only coding/text-capable chat models."""
    model = (rec.get("model") or "").lower()
    modality = (rec.get("modality") or "").lower()
    if modality in ("image", "audio", "video"):
        return False
    if modality == "vision":
        # vision-capable models are generally fine for coding too
        return True
    if any(t in model for t in EXCLUDE_TERMS):
        return False
    return True


PRICE_LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9.\-/ ]{0,60}?)\s*[:)]?\s*\$([\d.]+)", re.IGNORECASE)


def heuristic_extract(provider, text):
    """Fallback: parse columnar tables where model name line is followed by
    price value lines, e.g.
        GLM-5.3-Flash
        $0.15
        $0.03
        ...
    Returns list of records (one per model row)."""
    lines = [l.rstrip() for l in text.splitlines()]
    records = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        # a model-name line: no $ present, looks like an identifier/model
        if not line or "$" in line or "Price" in line.lower() or line.lower() in (
                "model", "input", "cached input", "output", "free"):
            i += 1
            continue
        # collect following price cells (until a non-price line or next model)
        prices = []
        j = i + 1
        while j < n:
            cell = lines[j].strip()
            low = cell.lower()
            if low == "free":
                prices.append("free")
                j += 1
            elif low in ("-", "\\", "/", "limited-time free", "n/a"):
                prices.append(None)
                j += 1
            elif re.match(r"^\$[\d.]+", cell):
                prices.append(float(re.search(r"[\d.]+", cell).group()))
                j += 1
            elif "free" in low and "$" in cell:
                prices.append(0.0)
                j += 1
            else:
                break
        if prices and any(ch.isdigit() for ch in line) and line.lower() not in (
                "model", "tool", "agent", "cost", "price", "input", "output"):
            # Columnar tables common order: Input, [Cached Input], [Storage], Output
            # Map: input=prices[0]; if >=3 prices, output=prices[-1] and cached=prices[1]
            num = len(prices)
            input_price = to_float(prices[0]) if num > 0 else None
            if num >= 3:
                output_price = to_float(prices[-1])
                cached_price = to_float(prices[1])
            elif num == 2:
                # likely Input, Output (no cached shown)
                output_price = to_float(prices[1])
                cached_price = None
            else:
                output_price = None
                cached_price = None
            rec = {
                "provider": provider,
                "model": line,
                "modality": "text",
                "input_price": input_price,
                "output_price": output_price,
                "cached_input_price": cached_price,
                "unit": "per_1M_tokens",
                "currency": "USD",
                "notes": "",
                "scraped_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            records.append(rec)
            i = j
        else:
            i += 1
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    raw_date = RAW_DIR / args.date
    if not raw_date.exists():
        sys.exit(f"No raw data for {args.date}")

    all_records = []
    for txt in sorted(raw_date.glob("*.txt")):
        provider = txt.stem
        text = txt.read_text(encoding="utf-8")
        print(f"Normalizing {provider}...")
        records = None
        if not args.no_llm:
            records = llm_extract(provider, text)
        if not records:
            records = heuristic_extract(provider, text)
            if records:
                print(f"  -> {len(records)} rows via heuristic fallback")
            else:
                print("  -> no records")
        coding = [r for r in records if is_coding_model(r)]
        if coding:
            print(f"  -> kept {len(coding)}/{len(records)} coding models")
        all_records.extend(coding)

    norm_dir = NORM_DIR / args.date
    norm_dir.mkdir(parents=True, exist_ok=True)
    out = norm_dir / "all.json"
    out.write_text(json.dumps(all_records, indent=2), encoding="utf-8")

    # append to history
    history = HIST_DIR / f"{args.date}.json"
    history.write_text(json.dumps(all_records, indent=2), encoding="utf-8")

    print(f"Wrote {len(all_records)} records -> {out}")
    print(f"History -> {history}")


if __name__ == "__main__":
    main()
