#!/usr/bin/env python3
"""Scrape AI provider pricing pages listed in sources.md.

Usage:
    python scripts/scrape.py                # today's date
    python scripts/scrape.py --date 2026-09-08
    python scripts/scrape.py [--provider z.ai] [--no-render]
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources.md"
RAW_DIR = ROOT / "data" / "raw"


def parse_sources(md_text: str):
    """Parse provider -> URL table from sources.md markdown."""
    providers = {}
    for line in md_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name, url = cells[0], cells[-1]
        if url.startswith("http") and name and name.lower() not in ("provider", "source link"):
            providers[name] = url
    return providers


def render_with_playwright(url: str, timeout_ms: int = 30000):
    """Load a JS-rendered page and return (html, text)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception:
            # fall back to domcontentloaded if networkidle times out
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        html = page.content()
        text = page.inner_text("body")
        browser.close()
        return html, text


def fetch_plain(url: str, timeout: int = 30):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    html = str(soup)
    text = soup.get_text("\n", strip=True)
    return html, text


def save(raw_date, provider, html, text):
    date_dir = RAW_DIR / raw_date
    date_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9_\-]+", "-", provider.lower()).strip("-")
    (date_dir / f"{safe}.html").write_text(html, encoding="utf-8")
    (date_dir / f"{safe}.txt").write_text(text, encoding="utf-8")
    return safe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--provider", help="scrape only one provider")
    ap.add_argument("--no-render", action="store_true", help="skip playwright, use requests only")
    args = ap.parse_args()

    if not SOURCES.exists():
        sys.exit(f"Missing sources file: {SOURCES}")
    providers = parse_sources(SOURCES.read_text(encoding="utf-8"))
    if not providers:
        sys.exit("No providers parsed from sources.md")

    if args.provider:
        providers = {k: v for k, v in providers.items() if k.lower() == args.provider.lower()}
        if not providers:
            sys.exit(f"Provider not found: {args.provider}")

    results = []
    for name, url in providers.items():
        for attempt in range(3):
            try:
                if args.no_render:
                    html, text = fetch_plain(url)
                else:
                    html, text = render_with_playwright(url)
                safe = save(args.date, name, html, text)
                results.append({"provider": name, "url": url, "file": safe, "ok": True})
                print(f"OK   {name}: {url}")
                break
            except Exception as exc:
                print(f"WARN {name} (attempt {attempt+1}): {exc}")
                time.sleep(2)
        else:
            results.append({"provider": name, "url": url, "ok": False, "error": "failed after retries"})

    out = RAW_DIR / args.date / "manifest.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["ok"])
    print(f"\nDone: {ok}/{len(results)} providers scraped -> {RAW_DIR / args.date}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
