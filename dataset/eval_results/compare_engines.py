"""
Loads all eval_results_<engine>.json files and produces a side-by-side
comparison CSV (compare_engines.csv) showing field presence rate per
doc_type × variant for each engine.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent

# Auto-discover all engine result files
engine_files = sorted(RESULTS_DIR.glob("eval_results_*.json"))
engines = [f.stem.replace("eval_results_", "") for f in engine_files]

if not engines:
    print("No eval_results_<engine>.json files found.")
    raise SystemExit(1)

print(f"Engines found: {engines}")

# Load all data
data = {}
for f, eng in zip(engine_files, engines):
    data[eng] = json.loads(f.read_text())["results"]

doc_types = ["pan", "aadhaar", "passbook", "invoice"]
variants   = ["clean", "rotated", "blurred", "compressed", "mobile_photo", "original"]


def avg_presence(results, doc_type, variant):
    rows = [r for r in results
            if r["doc_type"] == doc_type and r["variant"] == variant]
    if not rows:
        return None
    return sum(r["field_presence_rate"] for r in rows) / len(rows)


def fmt(v):
    return f"{v:.0%}" if v is not None else "-"


# ── 1. doc_type × engine (all variants combined) ──────────────────────────────
out1 = RESULTS_DIR / "compare_by_doctype.csv"
with open(out1, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["doc_type"] + engines)
    for dt in doc_types:
        row = [dt]
        for eng in engines:
            rates = [r["field_presence_rate"] for r in data[eng]
                     if r["doc_type"] == dt and r["ocr_success"]]
            row.append(fmt(sum(rates)/len(rates)) if rates else "-")
        w.writerow(row)
print(f"Saved: {out1.name}")


# ── 2. doc_type × variant × engine ────────────────────────────────────────────
out2 = RESULTS_DIR / "compare_by_variant.csv"
with open(out2, "w", newline="") as f:
    w = csv.writer(f)
    # Header: doc_type | variant | easyocr | paddleocr | tesseract | ...
    w.writerow(["doc_type", "variant"] + engines)
    for dt in doc_types:
        for v in variants:
            row = [dt, v]
            has_data = False
            for eng in engines:
                val = avg_presence(data[eng], dt, v)
                row.append(fmt(val))
                if val is not None:
                    has_data = True
            if has_data:
                w.writerow(row)
print(f"Saved: {out2.name}")


# ── 3. Overall summary ────────────────────────────────────────────────────────
print("\n── Field Presence Rate by Doc Type ─────────────────────────")
header = f"{'doc_type':<12}" + "".join(f"{e:>12}" for e in engines)
print(header)
print("-" * len(header))
for dt in doc_types:
    row = f"{dt:<12}"
    for eng in engines:
        rates = [r["field_presence_rate"] for r in data[eng]
                 if r["doc_type"] == dt and r["ocr_success"]]
        row += f"{fmt(sum(rates)/len(rates)) if rates else '-':>12}"
    print(row)
print("-" * len(header))
row = f"{'OVERALL':<12}"
for eng in engines:
    rates = [r["field_presence_rate"] for r in data[eng] if r["ocr_success"]]
    row += f"{fmt(sum(rates)/len(rates)) if rates else '-':>12}"
print(row)