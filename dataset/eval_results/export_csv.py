"""
Exports eval_results.json into three CSV files for Excel comparison.

  eval_per_image.csv   — one row per image, all field scores as columns
  eval_by_variant.csv  — field presence rate pivoted by doc_type × variant
  eval_by_field.csv    — per-field found rate broken down by doc_type × variant
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent
DATA = json.loads((RESULTS_DIR / "eval_results.json").read_text())
results = DATA["results"]

# ── 1. Per-image detail ───────────────────────────────────────────────────────
# Collect every field name that appears across all doc types
all_fields_by_type = defaultdict(set)
for r in results:
    for f in r.get("field_scores", {}):
        all_fields_by_type[r["doc_type"]].add(f)

per_image_path = RESULTS_DIR / "eval_per_image.csv"
with open(per_image_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    header = [
        "image", "doc_type", "variant", "side",
        "ocr_success", "ocr_chars",
        "predicted_doc_type", "classification_confidence_pct",
        "field_presence_rate",
        "fields_checked", "fields_found",
    ]
    # Add one column per field (ground_truth value + found flag)
    all_fields = sorted({f for fields in all_fields_by_type.values() for f in fields})
    for field in all_fields:
        header.append(f"{field}_gt")
        header.append(f"{field}_found")
    writer.writerow(header)

    for r in results:
        clf = r.get("classification") or {}
        fs  = r.get("field_scores", {})
        found_count   = sum(1 for s in fs.values() if s["found_in_text"])
        checked_count = len(fs)

        row = [
            r["image"],
            r["doc_type"],
            r["variant"],
            r["side"],
            r["ocr_success"],
            r["ocr_chars"],
            clf.get("predicted_type", ""),
            clf.get("confidence_pct", ""),
            r["field_presence_rate"],
            checked_count,
            found_count,
        ]
        for field in all_fields:
            score = fs.get(field)
            if score:
                row.append(score["ground_truth"])
                row.append("YES" if score["found_in_text"] else "NO")
            else:
                row.append("")
                row.append("")
        writer.writerow(row)

print(f"Saved: {per_image_path.name}  ({len(results)} rows)")


# ── 2. Summary pivot: doc_type × variant ─────────────────────────────────────
# Rows = doc types, Columns = variants
variants = ["clean", "rotated", "blurred", "compressed", "mobile_photo", "original"]
doc_types = ["pan", "aadhaar", "passbook", "invoice"]

# Build lookup: (doc_type, variant) → [field_presence_rates]
cell = defaultdict(list)
for r in results:
    cell[(r["doc_type"], r["variant"])].append(r["field_presence_rate"])

pivot_path = RESULTS_DIR / "eval_by_variant.csv"
with open(pivot_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    # Header
    writer.writerow(["doc_type \\ variant"] + variants + ["ALL VARIANTS"])
    for dt in doc_types:
        row = [dt]
        all_rates = []
        for v in variants:
            rates = cell[(dt, v)]
            if rates:
                avg = sum(rates) / len(rates)
                row.append(f"{avg:.0%}")
                all_rates.extend(rates)
            else:
                row.append("-")
        overall = f"{sum(all_rates)/len(all_rates):.0%}" if all_rates else "-"
        row.append(overall)
        writer.writerow(row)

    # Footer: variant averages
    row = ["ALL DOC TYPES"]
    all_overall = []
    for v in variants:
        rates = [r["field_presence_rate"] for r in results if r["variant"] == v]
        if rates:
            avg = sum(rates) / len(rates)
            row.append(f"{avg:.0%}")
            all_overall.extend(rates)
        else:
            row.append("-")
    row.append(f"{sum(all_overall)/len(all_overall):.0%}" if all_overall else "-")
    writer.writerow(row)

print(f"Saved: {pivot_path.name}")


# ── 3. Field-level breakdown: field × variant ─────────────────────────────────
field_path = RESULTS_DIR / "eval_by_field.csv"
with open(field_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["doc_type", "field"] + variants + ["ALL VARIANTS"])

    for dt in doc_types:
        fields = sorted(all_fields_by_type[dt])
        for field in fields:
            row = [dt, field]
            field_all = []
            for v in variants:
                hits = [
                    r["field_scores"][field]["found_in_text"]
                    for r in results
                    if r["doc_type"] == dt
                    and r["variant"] == v
                    and field in r.get("field_scores", {})
                ]
                if hits:
                    rate = sum(hits) / len(hits)
                    row.append(f"{rate:.0%}")
                    field_all.extend(hits)
                else:
                    row.append("-")
            overall = f"{sum(field_all)/len(field_all):.0%}" if field_all else "-"
            row.append(overall)
            writer.writerow(row)

print(f"Saved: {field_path.name}")
print("\nAll CSVs saved to:", RESULTS_DIR)