#!/usr/bin/env python3
"""Normalize scraped pricing text into a common JSON schema using an LLM.

LLM processing is MANDATORY (no heuristic fallback). Requires:
    BASE_URL  — OpenAI-compatible API base URL
    AI_MODEL  — model id
    AI_KEY    — API key

Only coding-capable models are kept, and duplicate models are removed
(cheapest entry wins).

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
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
NORM_DIR = ROOT / "data" / "normalized"
HIST_DIR = ROOT / "data" / "history"

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
AI_MODEL = os.environ.get("AI_MODEL", "").strip()
AI_KEY = os.environ.get("AI_KEY", "").strip()

SYSTEM_PROMPT = """You are a pricing-data extractor focused on CODING models.
Extract AI model pricing into JSON. KEEP ONLY models usable for CODING/LLM
text generation (chat/code models). EXCLUDE pure image/video/audio generation
models, embeddings, TTS, rerankers, storage pricing, grounding features and
other non-coding lines.
Return ONLY valid JSON, an array of objects with this exact schema:
{"provider": str, "model": str, "modality": "text|vision",
 "input_price": number|null, "output_price": number|null,
 "cached_input_price": number|null, "unit": "per_1M_tokens",
 "currency": "USD", "notes": str, "scraped_at": str}
Rules:
- The "model" field MUST be the actual model name (e.g. "Gemini 3.7 Flash",
  "GLM-5.3"). NEVER use table headers, column labels, notes or descriptions.
- Prices are per 1M tokens unless the page says otherwise. "Free" = 0.
  Empty/missing = null. If a range or future/current price exists, use the
  CURRENT price.
- Handle strikethrough discounts as current price (lowest published price).
- Do NOT invent models that are not on the page.
Example:
[{"provider":"z.ai","model":"GLM-5.3-Flash","modality":"text","input_price":0.075,
"output_price":0.25,"cached_input_price":0.015,"unit":"per_1M_tokens","currency":"USD",
"notes":"50% discount","scraped_at":"2026-09-08T00:00:00Z"}]"""

SCHEMA_FIELDS = ["provider", "model", "modality", "input_price", "output_price",
                 "cached_input_price", "unit", "currency", "notes", "scraped_at"]

EXCLUDE_TERMS = [
    "image", "video", "audio", "tts", "vocal", "speech", "asr", "transcrib",
    "embed", "rerank", "moderat", "flux", "dall-e", "sora", "veo", "cogvideo",
    "cogview", "seedream", "seedance", "kling", "wan ", "imagen", "nano banana",
    "gpt-image", "glm-ocr", "reranker",
]


def parse_completion_body(text):
    """Parse the first complete JSON object from an API body that may carry
    an SSE trailer like 'data: [DONE]' appended after the JSON object."""
    body = text.strip()
    for prefix in ("data:", "data :"):
        if body.startswith(prefix):
            body = body[len(prefix):].lstrip()
    if body.rstrip().endswith("data: [DONE]"):
        body = body.rstrip()[: -len("data: [DONE]")]
    decoder = json.JSONDecoder()
    # completion bodies are objects starting with '{'; scan for '{' first
    for m in re.finditer(r"[{\[]", body):
        try:
            obj, _ = decoder.raw_decode(body, m.start())
            if isinstance(obj, dict):  # prefer the outer completion object
                return obj
        except Exception:
            continue
    return None


def llm_extract(provider, text):
    """Use OpenAI-compatible LLM endpoint. Returns list of dicts or None."""
    if not BASE_URL or not AI_MODEL:
        return None
    user = f"Provider: {provider}\n\nScraped page text:\n{text[:10000]}"
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
    # BASE_URL may end with /chat/completions already, or point at the /v1 root
    endpoint = BASE_URL if BASE_URL.endswith("/chat/completions") else f"{BASE_URL}/chat/completions"
    for attempt in range(2):
        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=90)
            if not r.ok:
                print(f"  [llm] HTTP {r.status_code} for {provider} (attempt {attempt+1}): {r.text[:300]}", flush=True)
                continue
            obj = parse_completion_body(r.text)
            if not obj:
                print(f"  [llm] no JSON object for {provider} (attempt {attempt+1}): {r.text[:200]}", flush=True)
                continue
            content = obj["choices"][0]["message"]["content"]
            parsed = parse_llm_json(content, provider)
            if parsed:
                return parsed
            print(f"  [llm] unparseable JSON for {provider} (attempt {attempt+1}): {content[:200]}", flush=True)
        except Exception as exc:
            print(f"  [llm] error for {provider} (attempt {attempt+1}): {exc}", flush=True)
    return None


def parse_llm_json(content, provider):
    """Robustly extract a JSON array from an LLM response.

    The model may return extra text after the array (markdown fences, second
    code block, trailing notes). Find the first self-balanced JSON array and
    parse only that.
    """
    data = None
    try:
        data = json.loads(content)
    except Exception:
        pass
    if isinstance(data, list):
        return _rows_from_list(data, provider)
    for arr in _scan_json_arrays(content):
        data = arr
        break
    if isinstance(data, list):
        return _rows_from_list(data, provider)
    return None


def _scan_json_arrays(text):
    """Yield substrings that are full balanced JSON arrays, in order."""
    for m in re.finditer(r"\[", text):
        try:
            decoder = json.JSONDecoder()
            obj, end = decoder.raw_decode(text, m.start())
            yield obj
        except Exception:
            continue


def _rows_from_list(data, provider):
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        row["provider"] = provider
        for f in SCHEMA_FIELDS:
            row.setdefault(f, None if f != "currency" else "USD")
        out.append(row)
    return out


def is_coding_model(rec):
    """Keep only coding/text-capable chat models."""
    model = (rec.get("model") or "").lower()
    modality = (rec.get("modality") or "").lower()
    if modality in ("image", "audio", "video"):
        return False
    if any(t in model for t in EXCLUDE_TERMS):
        return False
    return True


def price_key(rec):
    out = rec.get("output_price")
    if isinstance(out, (int, float)):
        return (0, out)
    inp = rec.get("input_price")
    if isinstance(inp, (int, float)):
        return (1, inp)
    return (2, float("inf"))


def dedupe_models(records):
    """Remove duplicate models across providers; keep the cheapest entry."""
    best = {}
    for rec in records:
        key = (rec.get("model") or "").strip().lower()
        if not key:
            continue
        cur = best.get(key)
        if cur is None or price_key(rec) < price_key(cur):
            best[key] = rec
    return list(best.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    if not BASE_URL or not AI_MODEL:
        sys.exit("ERROR: BASE_URL and AI_MODEL env vars are required (LLM processing is mandatory).")

    raw_date = RAW_DIR / args.date
    if not raw_date.exists():
        sys.exit(f"No raw data for {args.date}")

    all_records = []
    failed = []

    def process(txt):
        provider = txt.stem
        text = txt.read_text(encoding="utf-8")
        print(f"Normalizing {provider}...", flush=True)
        records = llm_extract(provider, text)
        return provider, records

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(process, txt) for txt in sorted(raw_date.glob("*.txt"))]
        for fut in as_completed(futures):
            provider, records = fut.result()
            if not records:
                print(f"  !! LLM returned no usable records for {provider}", flush=True)
                failed.append(provider)
                continue
            coding = [r for r in records if is_coding_model(r)]
            print(f"  -> {len(coding)}/{len(records)} coding models extracted ({provider})", flush=True)
            all_records.extend(coding)

    all_records = dedupe_models(all_records)
    print(f"After dedupe: {len(all_records)} unique models")

    norm_dir = NORM_DIR / args.date
    norm_dir.mkdir(parents=True, exist_ok=True)
    out = norm_dir / "all.json"
    out.write_text(json.dumps(all_records, indent=2), encoding="utf-8")

    history = HIST_DIR / f"{args.date}.json"
    history.write_text(json.dumps(all_records, indent=2), encoding="utf-8")

    print(f"Wrote {len(all_records)} records -> {out}")
    print(f"History -> {history}")

    if failed:
        print(f"WARNING: LLM failed for: {', '.join(failed)}")
    if not all_records:
        sys.exit("ERROR: no records extracted — aborting to avoid committing empty/garbage data.")


if __name__ == "__main__":
    main()