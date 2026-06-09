"""
PAN card generator — produces five image variants per employee:
  clean        → sharp card on white background
  rotated      → random tilt  (-12° … +12°)
  blurred      → gaussian blur with random radius (1.5 … 4.0)
  compressed   → JPEG artefacts with random quality (20 … 50)
  mobile_photo → perspective warp + slight blur + vignette + partial crop

Output layout:
  generated_docs/pan/  EMP001_pan_clean.png
                       EMP001_pan_rotated.png
                       EMP001_pan_blurred.png
                       EMP001_pan_compressed.jpg
                       EMP001_pan_mobile_photo.jpg

Ground truth:
  ground_truth/pan/    EMP001_pan.json
"""

import csv
import io
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "employees.csv"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth" / "pan"

GENERATED_DOCS_DIR = BASE_DIR / "generated_docs" / "pan"

for d in [GROUND_TRUTH_DIR, GENERATED_DOCS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FONT_REGULAR = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"

CARD_W, CARD_H = 1012, 638


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def load_employees(limit=None):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


VARIANT_EXT = {
    "clean":        "png",
    "rotated":      "png",
    "blurred":      "png",
    "compressed":   "jpg",
    "mobile_photo": "jpg",
}


def save_ground_truth(emp):
    eid = emp["employee_id"]
    data = {
        "pan_number":    emp["pan_number"],
        "name":          f"{emp['first_name']} {emp['last_name']}",
        "father_name":   emp["father_name"],
        "date_of_birth": emp["dob"],
        "gender":        emp["gender"],
        "source_images": [
            f"{eid}_pan_{variant}.{ext}"
            for variant, ext in VARIANT_EXT.items()
        ],
    }
    out = GROUND_TRUTH_DIR / f"{eid}_pan.json"
    out.write_text(json.dumps(data, indent=4, ensure_ascii=False))
    return data


# ── Base card renderer ────────────────────────────────────────────────────────

def render_pan_card(data):
    """Returns a clean PIL Image of the PAN card."""
    img = Image.new("RGB", (CARD_W, CARD_H), "#FFFDE7")
    draw = ImageDraw.Draw(img)

    f_title  = load_font(FONT_BOLD,    30)
    f_sub    = load_font(FONT_REGULAR, 19)
    f_label  = load_font(FONT_REGULAR, 21)
    f_value  = load_font(FONT_BOLD,    23)
    f_pan    = load_font(FONT_BOLD,    46)
    f_tiny   = load_font(FONT_REGULAR, 17)

    # Header
    draw.rectangle([0, 0, CARD_W, 105], fill="#1A3A6C")
    draw.ellipse([18, 10, 90, 94],  fill="#FFFFFF", outline="#C8A000", width=3)
    draw.ellipse([30, 22, 78, 82],  outline="#C8A000", width=2)
    draw.text((108, 14), "INCOME TAX DEPARTMENT", font=f_title, fill="#FFFFFF")
    draw.text((108, 54), "GOVT. OF INDIA",         font=f_sub,   fill="#C8C8C8")
    draw.rectangle([0, 105, CARD_W, 109], fill="#C8A000")

    # Photo placeholder
    draw.rectangle([30, 125, 210, 310], fill="#E0E0E0", outline="#AAAAAA", width=2)
    draw.text((75, 205), "PHOTO", font=f_tiny, fill="#888888")

    # Fields
    x, y = 240, 128
    for label, value in [
        ("Name",          data["name"].upper()),
        ("Father's Name", data["father_name"].upper()),
        ("Date of Birth", data["date_of_birth"]),
    ]:
        draw.text((x, y),      label, font=f_label, fill="#555555")
        draw.text((x, y + 26), value, font=f_value, fill="#111111")
        draw.line([x, y + 54, CARD_W - 30, y + 54], fill="#CCCCCC", width=1)
        y += 68

    # Signature box
    draw.rectangle([x, y + 10, x + 240, y + 65], outline="#AAAAAA", width=1)
    draw.text((x + 60, y + 24), "SIGNATURE", font=f_tiny, fill="#AAAAAA")

    # Footer
    fy = CARD_H - 130
    draw.rectangle([0, fy, CARD_W, CARD_H], fill="#1A3A6C")
    draw.rectangle([0, fy, CARD_W, fy + 4],  fill="#C8A000")
    draw.text((55, fy + 10), "Permanent Account Number", font=f_tiny,  fill="#AAAAAA")
    draw.text((55, fy + 34), data["pan_number"],          font=f_pan,   fill="#FFFFFF")
    draw.text((CARD_W - 190, fy + 34), data["gender"].upper(), font=f_value, fill="#AAAAAA")

    return img


# ── Variant transforms ────────────────────────────────────────────────────────

def apply_clean(img):
    """No modifications — sharp PNG."""
    return img.copy(), "png"


def apply_rotated(img, rng):
    """Random tilt on a white canvas."""
    angle = rng.uniform(-12, 12)
    rotated = img.rotate(angle, expand=True, fillcolor=(255, 255, 255),
                         resample=Image.BICUBIC)
    return rotated, "png"


def apply_blurred(img, rng):
    """Gaussian blur with a random radius."""
    radius = rng.uniform(1.5, 4.0)
    return img.filter(ImageFilter.GaussianBlur(radius=radius)), "png"


def apply_compressed(img, rng):
    """Re-encode as JPEG with random low quality to introduce artefacts."""
    quality = rng.randint(20, 50)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).copy(), "jpg"


def _perspective_coeffs(src_quad, dst_quad):
    """
    Compute the 8 perspective transform coefficients that map src_quad → dst_quad.
    Each quad is [(x0,y0), (x1,y1), (x2,y2), (x3,y3)] (TL, BL, BR, TR).
    PIL's PERSPECTIVE transform uses the inverse mapping (dst → src), so we
    compute src_to_dst then invert it.
    """
    # Build the 8×8 linear system  A·h = b
    A, b = [], []
    for (sx, sy), (dx, dy) in zip(src_quad, dst_quad):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        b.append(dx)
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        b.append(dy)
    h = np.linalg.solve(np.array(A, dtype=float), np.array(b, dtype=float))
    return tuple(h)


def _vignette(img, strength=0.55):
    """Darken the edges to simulate a phone lens."""
    arr = np.array(img, dtype=np.float32)
    H, W = arr.shape[:2]
    Y, X = np.ogrid[:H, :W]
    cx, cy = W / 2, H / 2
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    mask = 1 - np.clip(dist * strength, 0, 1)
    mask = mask[:, :, np.newaxis]
    arr = np.clip(arr * mask, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_mobile_photo(img, rng):
    """
    Simulate a hand-held phone shot:
      1. Perspective warp (random trapezoid distortion)
      2. Slight random rotation (±5°)
      3. Mild Gaussian blur
      4. Vignette
      5. Random partial crop from one or two edges
    """
    W, H = img.size

    # 1. Perspective warp — shift corners by random offsets
    max_shift = int(min(W, H) * 0.07)

    def shift():
        return rng.randint(-max_shift, max_shift)

    src = [(0, 0), (0, H), (W, H), (W, 0)]
    dst = [
        (shift(), shift()),           # TL
        (shift(), H + shift()),       # BL
        (W + shift(), H + shift()),   # BR
        (W + shift(), shift()),       # TR
    ]
    coeffs = _perspective_coeffs(src, dst)
    warped = img.transform((W, H), Image.PERSPECTIVE, coeffs,
                           resample=Image.BICUBIC, fillcolor=(230, 230, 220))

    # 2. Slight rotation
    angle = rng.uniform(-5, 5)
    warped = warped.rotate(angle, expand=False, fillcolor=(230, 230, 220),
                           resample=Image.BICUBIC)

    # 3. Mild blur
    radius = rng.uniform(0.8, 2.2)
    warped = warped.filter(ImageFilter.GaussianBlur(radius=radius))

    # 4. Vignette
    warped = _vignette(warped, strength=rng.uniform(0.4, 0.65))

    # 5. Partial crop from 1–2 random edges
    sides = rng.sample(["top", "bottom", "left", "right"], k=rng.randint(1, 2))
    left = top = 0
    right, bottom = W, H
    crop_frac = rng.uniform(0.04, 0.10)
    for side in sides:
        if side == "top":    top    = int(H * crop_frac)
        if side == "bottom": bottom = int(H * (1 - crop_frac))
        if side == "left":   left   = int(W * crop_frac)
        if side == "right":  right  = int(W * (1 - crop_frac))
    warped = warped.crop((left, top, right, bottom))

    # Re-encode as JPEG (phones save JPEG)
    quality = rng.randint(55, 80)
    buf = io.BytesIO()
    warped.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).copy(), "jpg"


# ── Main ─────────────────────────────────────────────────────────────────────

TRANSFORMS = {
    "clean":        lambda img, rng: apply_clean(img),
    "rotated":      apply_rotated,
    "blurred":      apply_blurred,
    "compressed":   apply_compressed,
    "mobile_photo": apply_mobile_photo,
}


def process_employee(emp, rng):
    eid = emp["employee_id"]
    data = save_ground_truth(emp)
    base = render_pan_card(data)

    for variant, transform in TRANSFORMS.items():
        result, ext = transform(base, rng)
        out_path = GENERATED_DOCS_DIR / f"{eid}_pan_{variant}.{ext}"
        result.save(out_path)
        print(f"  [{variant:>12}]  {out_path.name}")


def main(limit=2):
    rng = random.Random(42)
    employees = load_employees(limit=limit)
    for emp in employees:
        print(f"\n{emp['employee_id']} — {emp['first_name']} {emp['last_name']}")
        process_employee(emp, rng)
    print("\nDone.")


if __name__ == "__main__":
    main(limit=2)