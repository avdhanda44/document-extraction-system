"""
Evaluation script — runs all dataset images through the extraction pipeline
and compares results against ground truth to produce accuracy metrics.

Measured per image:
  - ocr_success       : was any text extracted?
  - classification    : what document type did the pipeline predict?
  - field_presence    : for each GT field value, does it appear in the OCR text?
  - field_presence_rate : % of GT fields found in OCR text (0-1)

Aggregated in summary:
  - by doc type   (pan / aadhaar / passbook / invoice)
  - by variant    (clean / rotated / blurred / compressed / mobile_photo / original)

Output saved to:  dataset/eval_results/eval_results.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── Make Backend importable from project root ─────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from Backend.processor.text_extractor import (
    detect_uploaded_file_type,
    extract_text_by_file_type,
)
from Backend.extractor.document_classification import choose_document_type_from_text

EVAL_OUT_DIR = ROOT / "dataset" / "eval_results"
EVAL_OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Dataset locations ─────────────────────────────────────────────────────────
DATASETS = {
    "pan": {
        "images_dir": ROOT / "dataset/employee_docs/generated_docs/pan",
        "gt_dir":     ROOT / "dataset/employee_docs/ground_truth/pan",
        "gt_fields":  ["pan_number", "name", "date_of_birth", "gender"],
    },
    "aadhaar": {
        "images_dir": ROOT / "dataset/employee_docs/generated_docs/aadhaar",
        "gt_dir":     ROOT / "dataset/employee_docs/ground_truth/aadhaar",
        "gt_fields":  ["aadhaar_number", "name", "date_of_birth", "gender", "address"],
    },
    "passbook": {
        "images_dir": ROOT / "dataset/employee_docs/generated_docs/passbook",
        "gt_dir":     ROOT / "dataset/employee_docs/ground_truth/passbook",
        "gt_fields":  ["account_number", "ifsc", "account_holder", "pan_number"],
    },
    "invoice": {
        "images_dir": ROOT / "dataset/invoice_docs/invoices",
        "gt_dir":     ROOT / "dataset/invoice_docs/ground_truth",
        "gt_fields":  ["company", "date", "total"],
    },
}


# ── Ground truth lookup ───────────────────────────────────────────────────────

def find_ground_truth(image_path: Path, gt_dir: Path, doc_type: str) -> dict | None:
    """
    Map an image filename back to its ground truth JSON.

    Naming conventions:
      pan        EMP001_pan_clean.png          → EMP001_pan.json
      aadhaar    EMP001_aadhaar_front_clean.png → EMP001_aadhaar.json
      passbook   EMP001_passbook_clean.png      → EMP001_passbook.json
      invoice    X00016469672.jpg               → X00016469672.json
    """
    stem = image_path.stem  # e.g. "EMP001_pan_clean"

    known_variants = ["mobile_photo", "clean", "rotated", "blurred", "compressed"]

    def strip_variant(s):
        for v in known_variants:
            if s.endswith(f"_{v}"):
                return s[: -(len(v) + 1)]
        return s

    if doc_type == "invoice":
        # Invoice images keep their original filename — stem = gt stem directly
        gt_path = gt_dir / f"{stem}.json"
        if not gt_path.exists():
            # Also try source_image field by scanning all gt files
            for gt_file in gt_dir.glob("*.json"):
                try:
                    d = json.loads(gt_file.read_text())
                    if d.get("source_image") == image_path.name:
                        gt_path = gt_file
                        break
                except Exception:
                    continue
    elif doc_type == "pan":
        # EMP001_pan_<variant> → EMP001_pan
        gt_path = gt_dir / f"{strip_variant(stem)}.json"
    elif doc_type == "aadhaar":
        # EMP001_aadhaar_front_<variant> → EMP001_aadhaar
        # strip variant first, then strip _front / _back
        base = strip_variant(stem)                      # EMP001_aadhaar_front
        base = base.rsplit("_", 1)[0]                  # EMP001_aadhaar
        gt_path = gt_dir / f"{base}.json"
    elif doc_type == "passbook":
        # EMP001_passbook_<variant> → EMP001_passbook
        gt_path = gt_dir / f"{strip_variant(stem)}.json"
    else:
        return None

    if not gt_path.exists():
        return None
    try:
        return json.loads(gt_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_variant(image_path: Path, doc_type: str) -> str:
    stem = image_path.stem
    known = ["clean", "rotated", "blurred", "compressed", "mobile_photo"]
    for v in known:
        if stem.endswith(f"_{v}"):
            return v
    return "original"


def extract_side(image_path: Path, doc_type: str) -> str:
    if doc_type == "aadhaar":
        if "_front_" in image_path.stem:
            return "front"
        if "_back_" in image_path.stem:
            return "back"
    return "n/a"


# ── Field presence check ──────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for loose matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def value_found_in_text(gt_value: str, ocr_text: str) -> bool:
    """
    Return True if the ground truth value is present in OCR text.
    Strategy:
      1. Exact normalized match (handles minor OCR spacing issues)
      2. All significant tokens present (handles reordered / split text)
    """
    if not gt_value or not ocr_text:
        return False

    norm_gt  = normalize(gt_value)
    norm_ocr = normalize(ocr_text)

    # Exact match after normalization
    if norm_gt in norm_ocr:
        return True

    # Token-level: every word of the GT value appears in the OCR text
    tokens = [t for t in norm_gt.split() if len(t) > 1]
    if tokens and all(t in norm_ocr for t in tokens):
        return True

    return False


def score_fields(gt: dict, ocr_text: str, fields_to_check: list) -> dict:
    scores = {}
    for field in fields_to_check:
        gt_value = str(gt.get(field, "")).strip()
        if gt_value:
            found = value_found_in_text(gt_value, ocr_text)
            scores[field] = {
                "ground_truth": gt_value,
                "found_in_text": found,
            }
    return scores


# ── Per-image evaluation ──────────────────────────────────────────────────────

def evaluate_image(image_path: Path, doc_type: str, cfg: dict) -> dict:
    gt = find_ground_truth(image_path, cfg["gt_dir"], doc_type)
    variant = extract_variant(image_path, doc_type)
    side    = extract_side(image_path, doc_type)

    result = {
        "image":       image_path.name,
        "doc_type":    doc_type,
        "variant":     variant,
        "side":        side,
        "ocr_success": False,
        "ocr_chars":   0,
        "classification": None,
        "field_scores": {},
        "field_presence_rate": 0.0,
        "error": None,
    }

    # ── Step 1: OCR / text extraction ────────────────────────────
    try:
        file_type = detect_uploaded_file_type(image_path)
        if file_type == "unknown":
            # Fallback: guess from extension
            ext = image_path.suffix.lower().lstrip(".")
            file_type = ext if ext in ("pdf", "png", "jpg", "docx") else "jpg"
        ocr_text = extract_text_by_file_type(image_path, file_type)
    except Exception as e:
        result["error"] = f"OCR failed: {e}"
        return result

    result["ocr_success"] = bool(ocr_text and ocr_text.strip())
    result["ocr_chars"]   = len(ocr_text.strip()) if ocr_text else 0

    if not result["ocr_success"]:
        result["error"] = "No text extracted"
        return result

    # ── Step 2: document classification ──────────────────────────
    try:
        clf = choose_document_type_from_text(ocr_text)
        result["classification"] = {
            "predicted_type":    clf["document_type"],
            "confidence_pct":    clf["confidence_percent"],
            "confidence_level":  clf["confidence_level"],
        }
    except Exception as e:
        result["classification"] = {"error": str(e)}

    # ── Step 3: field presence scoring ───────────────────────────
    if gt:
        field_scores = score_fields(gt, ocr_text, cfg["gt_fields"])
        result["field_scores"] = field_scores
        if field_scores:
            found = sum(1 for s in field_scores.values() if s["found_in_text"])
            result["field_presence_rate"] = round(found / len(field_scores), 4)
    else:
        result["error"] = (result.get("error") or "") + " | ground truth not found"

    return result


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate(results: list) -> dict:
    def avg(vals):
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    total = len(results)
    ocr_ok = [r for r in results if r["ocr_success"]]

    # By doc type
    by_type = {}
    for doc_type in DATASETS:
        group = [r for r in results if r["doc_type"] == doc_type]
        if not group:
            continue
        by_type[doc_type] = {
            "total_images":        len(group),
            "ocr_success_count":   sum(1 for r in group if r["ocr_success"]),
            "ocr_success_rate":    avg([1 if r["ocr_success"] else 0 for r in group]),
            "avg_field_presence":  avg([r["field_presence_rate"] for r in group if r["ocr_success"]]),
        }

    # By variant
    by_variant = {}
    all_variants = {r["variant"] for r in results}
    for variant in sorted(all_variants):
        group = [r for r in results if r["variant"] == variant]
        by_variant[variant] = {
            "total_images":       len(group),
            "ocr_success_rate":   avg([1 if r["ocr_success"] else 0 for r in group]),
            "avg_field_presence": avg([r["field_presence_rate"] for r in group if r["ocr_success"]]),
        }

    return {
        "total_images":        total,
        "ocr_success_count":   len(ocr_ok),
        "ocr_success_rate":    avg([1 if r["ocr_success"] else 0 for r in results]),
        "avg_field_presence":  avg([r["field_presence_rate"] for r in ocr_ok]),
        "by_doc_type":         by_type,
        "by_variant":          by_variant,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main(engine: str = "easyocr"):
    print(f"\nOCR ENGINE: {engine.upper()}")
    all_results = []
    image_exts  = {".png", ".jpg", ".jpeg", ".pdf"}

    for doc_type, cfg in DATASETS.items():
        images_dir = cfg["images_dir"]
        if not images_dir.exists():
            print(f"  [skip] {doc_type} — images dir not found: {images_dir}")
            continue

        images = sorted(p for p in images_dir.iterdir()
                        if p.suffix.lower() in image_exts)
        print(f"\n{doc_type.upper()} — {len(images)} images")

        for img_path in images:
            print(f"  {img_path.name} ...", end=" ", flush=True)
            result = evaluate_image(img_path, doc_type, cfg)
            all_results.append(result)

            fpr = result["field_presence_rate"]
            ocr = "✓" if result["ocr_success"] else "✗"
            print(f"{ocr}  field presence: {fpr:.0%}  "
                  f"({result.get('error') or ''})")

    summary = aggregate(all_results)

    output = {
        "engine":  engine,
        "summary": summary,
        "results": all_results,
    }

    out_path = EVAL_OUT_DIR / f"eval_results_{engine}.json"
    out_path.write_text(json.dumps(output, indent=4, ensure_ascii=False))

    # ── Print summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total images       : {summary['total_images']}")
    print(f"OCR success        : {summary['ocr_success_count']} "
          f"({summary['ocr_success_rate']:.0%})")
    print(f"Avg field presence : {summary['avg_field_presence']:.0%}")
    print("\nBy document type:")
    for dt, s in summary["by_doc_type"].items():
        print(f"  {dt:<12}  ocr={s['ocr_success_rate']:.0%}  "
              f"field_presence={s['avg_field_presence']:.0%}  "
              f"({s['total_images']} images)")
    print("\nBy variant:")
    for v, s in summary["by_variant"].items():
        print(f"  {v:<14}  ocr={s['ocr_success_rate']:.0%}  "
              f"field_presence={s['avg_field_presence']:.0%}")
    print(f"\nFull results saved to: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate OCR pipeline against ground truth.")
    parser.add_argument(
        "--engine",
        choices=["easyocr", "paddleocr", "tesseract"],
        default="easyocr",
        help="OCR engine to use (default: easyocr)",
    )
    cli_args = parser.parse_args()
    os.environ["OCR_ENGINE"] = cli_args.engine
    main(engine=cli_args.engine)