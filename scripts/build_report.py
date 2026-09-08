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
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NORM_DIR = ROOT / "data" / "normalized"
HIST_DIR = ROOT / "data" / "history"
PRICING = ROOT / "pricing.md"


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

    records = json.loads(in_file.read_text(encoding="utf-8"))
    # normalizing provider names to display form
    records.sort(key=sort_key)

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
    if changes:
        print(f"{len(changes)} price change(s) detected vs {prev}")


if __name__ == "__main__":
    main()
