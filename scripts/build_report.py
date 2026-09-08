#!/usr/bin/env python3
"""Build pricing.md (root) from normalized data, sorted cheapest -> most expensive.

Also runs change detection against the previous day's history.

Usage:
    python scripts/build_report.py --date 2026-09-08
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NORM_DIR = ROOT / "data" / "normalized"
HIST_DIR = ROOT / "data" / "history"
PRICING = ROOT / "pricing.md"
BEST_PRICING = ROOT / "pricing-best-models.md"
SOURCES = ROOT / "sources.md"


def best_models():
    """Parse the 'Best Coding Models' table from sources.md into {lower_name: name}."""
    text = SOURCES.read_text(encoding="utf-8")
    best = {}
    in_best = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Best Coding Models"):
            in_best = True
            continue
        if in_best and stripped.startswith("## "):
            break
        if in_best and stripped.startswith("|") and "--" not in stripped:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].isdigit():
                name = cells[1]
                best[name.lower()] = name
    return best


def tokens(name):
    return [t for t in re.split(r"[^0-9a-z]+", name.lower()) if t]


def matches_best(model, best):
    """Match a normalized model name to one of the best-model names.

    Token-prefix match (version-aware) preferring the most specific name:
    'glm-5.3-flash' matches both 'glm-5.3' and 'glm-5.3-flash', picks the
    longer; 'glm-5' does NOT match 'glm-5.3'.
    """
    m = tokens(model or "")
    if not m:
        return None
    matched = None
    for b, bname in best.items():
        bt = tokens(b)
        if len(bt) > len(m) or m[: len(bt)] != bt:
            continue
        if len(m) > len(bt):
            nxt = m[len(bt)]
            # don't allow a version extension (5 → 5.3) to count as a match
            if bt and bt[-1].isdigit() and nxt.isdigit():
                continue
        if matched is None or len(bname) > len(matched):
            matched = bname
    return matched


def sort_key(rec):
    """Canonical metric: output_price if present, else input_price, else inf."""
    out = rec.get("output_price")
    if isinstance(out, (int, float)):
        return out
    inp = rec.get("input_price")
    if isinstance(inp, (int, float)):
        return inp
    return float("inf")


def fmt_price(v):
    if v is None:
        return "-"
    return "Free" if v == 0 else f"${v:g}"


def compare_prev(date_str, records):
    """Return list of changes vs previous day."""
    all_dates = sorted(d.stem for d in HIST_DIR.glob("*.json")) if HIST_DIR.exists() else []
    prev = None
    for d in reversed(all_dates):
        if d < date_str:
            prev = d
            break
    if not prev:
        return [], None
    old = {}
    for rec in json.loads((HIST_DIR / f"{prev}.json").read_text(encoding="utf-8")):
        old[(rec.get("provider"), rec.get("model"))] = rec
    changes = []
    for rec in records:
        key = (rec.get("provider"), rec.get("model"))
        if key in old:
            o = old[key]
            no = rec.get("output_price")
            oo = o.get("output_price")
            ni = rec.get("input_price")
            oi = o.get("input_price")
            if no != oo or ni != oi:
                changes.append({
                    "provider": rec.get("provider"), "model": rec.get("model"),
                    "input": {"from": oi, "to": ni}, "output": {"from": oo, "to": no},
                })
    return changes, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    in_file = NORM_DIR / args.date / "all.json"
    if not in_file.exists():
        sys.exit(f"No normalized data for {args.date}: {in_file}")

    raw = json.loads(in_file.read_text(encoding="utf-8"))
    # defensive dedupe: same model name from multiple providers → cheapest wins
    seen = {}
    for rec in raw:
        key = (rec.get("model") or "").strip().lower()
        if not key:
            continue
        cur = seen.get(key)
        if cur is None or sort_key(rec) < sort_key(cur):
            seen[key] = rec
    records = list(seen.values())
    records.sort(key=sort_key)

    best = best_models()
    best_records = [
        {"best_name": name, "rec": rec}
        for rec in raw
        for name in [matches_best(rec.get("model"), best)]
        if name
    ]
    best_records.sort(key=lambda br: sort_key(br["rec"]))

    by_modality = {}
    for rec in records:
        by_modality.setdefault(rec.get("modality", "text"), []).append(rec)

    lines = []
    lines.append("# AI Catalog Pricing")
    lines.append("")
    lines.append(f"_Generated: {args.date} 00:00 UTC · sorted cheapest → most expensive_")
    lines.append("")
    lines.append(f"**{len(records)} models** tracked from **{len(set(r['provider'] for r in records))} providers**.")
    lines.append("")
    lines.append("| Rank | Provider | Model | Input | Output | Cached | Unit | Notes |")
    lines.append("|------|----------|-------|-------|--------|--------|------|-------|")
    rank = 0
    for rec in records:
        rank += 1
        notes = (rec.get("notes") or "").replace("\n", " ")[:40]
        lines.append(
            f"| {rank} | {rec.get('provider','')} | {rec.get('model','')} "
            f"| {fmt_price(rec.get('input_price'))} | {fmt_price(rec.get('output_price'))} "
            f"| {fmt_price(rec.get('cached_input_price'))} | {rec.get('unit','')} | {notes} |"
        )
    lines.append("")
    lines.append("## Change Detection")
    changes, prev = compare_prev(args.date, records)
    if changes:
        lines.append(f"Compared to {prev}, **{len(changes)}** price change(s):")
        lines.append("")
        lines.append("| Provider | Model | Input (from→to) | Output (from→to) |")
        lines.append("|----------|-------|-----------------|-----------------|")
        for c in changes:
            lines.append(
                f"| {c['provider']} | {c['model']} | "
                f"{fmt_price(c['input']['from'])} → {fmt_price(c['input']['to'])} | "
                f"{fmt_price(c['output']['from'])} → {fmt_price(c['output']['to'])} |"
            )
    else:
        lines.append(f"No price changes detected vs previous day ({prev or 'n/a'}).")
    lines.append("")

    PRICING.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {PRICING} with {len(records)} records sorted cheapest → most expensive")

    write_best_pricing(args.date, best_records)

    if changes:
        print(f"{len(changes)} price change(s) detected vs {prev}")


def write_best_pricing(date_str, best_records):
    """Write pricing-best-models.md: only the top best coding models,
    listed cheapest → most expensive with the offering providers."""
    rows = []
    seen = set()
    for br in best_records:
        rec = br["rec"]
        key = (rec.get("model") or "").strip().lower()
        if key in seen:
            continue  # same provider/model already listed
        seen.add(key)
        rows.append((br["best_name"], rec))
    rows.sort(key=lambda r: sort_key(r[1]))

    lines = []
    lines.append("# AI Catalog Pricing — Best Coding Models")
    lines.append("")
    lines.append(f"_Generated: {date_str} 00:00 UTC · best coding models, sorted cheapest → most expensive_")
    lines.append("")
    models = set(r[0] for r in rows)
    lines.append(f"**{len(models)} best coding models** offered by **{len(set(r[1]['provider'] for r in rows))} providers**.")
    lines.append("")
    lines.append("| Rank | Best Model | Provider | Input | Output | Cached | Unit | Notes |")
    lines.append("|------|------------|----------|-------|--------|--------|------|-------|")
    rank = 0
    for best_name, rec in rows:
        rank += 1
        notes = (rec.get("notes") or "").replace("\n", " ")[:40]
        lines.append(
            f"| {rank} | {best_name} | {rec.get('provider','')} "
            f"| {fmt_price(rec.get('input_price'))} | {fmt_price(rec.get('output_price'))} "
            f"| {fmt_price(rec.get('cached_input_price'))} | {rec.get('unit','')} | {notes} |"
        )
    lines.append("")
    missing = [name for name in best_models().values() if name.lower() not in {r[0].lower() for r in rows}]
    if missing:
        lines.append(f"Not found in today's catalog: {', '.join(missing)}")
        lines.append("")
        lines.append("_Providers may list these models on pages the scraper missed, or pricing is not public._")
        lines.append("")

    BEST_PRICING.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {BEST_PRICING} with {len(models)} best models (from {len(rows)} provider offers)")


if __name__ == "__main__":
    main()
