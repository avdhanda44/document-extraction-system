"""
Aadhaar card generator — front + back sides, five variants each.

Output:
  generated_docs/aadhaar/  EMP001_aadhaar_front_clean.png
                           EMP001_aadhaar_front_rotated.png
                           EMP001_aadhaar_front_blurred.png
                           EMP001_aadhaar_front_compressed.jpg
                           EMP001_aadhaar_front_mobile_photo.jpg
                           EMP001_aadhaar_back_*.{png,jpg}
                           ...

Ground truth:
  ground_truth/aadhaar/    EMP001_aadhaar.json
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
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth" / "aadhaar"
GENERATED_DOCS_DIR = BASE_DIR / "generated_docs" / "aadhaar"

for d in [GROUND_TRUTH_DIR, GENERATED_DOCS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FONT_REGULAR   = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD      = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_DEVA      = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"
FONT_DEVA_BOLD = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"

CARD_W, CARD_H = 1012, 638

BG_COLOR      = "#C8B49A"
SAFFRON       = "#FF9933"
INDIA_GREEN   = "#138808"
AADHAAR_RED   = "#E03030"
DARK_TEXT     = "#1A1A1A"
MUTED_TEXT    = "#555555"
HEADER_H      = 92
NUM_BAND_Y    = 460
TAG_BAND_Y    = 540

VARIANTS = ["clean", "rotated", "blurred", "compressed", "mobile_photo"]
VARIANT_EXT = {
    "clean":        "png",
    "rotated":      "png",
    "blurred":      "png",
    "compressed":   "jpg",
    "mobile_photo": "jpg",
}

HINDI_FIRST = {
    "Priya": "प्रिया", "Rohit": "रोहित", "Anjali": "अंजली",
    "Vikram": "विक्रम", "Sneha": "स्नेहा", "Arjun": "अर्जुन",
    "Pooja": "पूजा",   "Karthik": "कार्तिक", "Ritu": "रितु",
    "Suresh": "सुरेश",
}
HINDI_LAST = {
    "Sharma": "शर्मा", "Verma": "वर्मा", "Nair": "नायर",
    "Singh": "सिंह",   "Iyer": "अय्यर",  "Mehta": "मेहता",
    "Reddy": "रेड्डी", "Pillai": "पिल्लई", "Gupta": "गुप्ता",
    "Rao": "राव",
}
HINDI_GENDER = {"Male": "पुरुष", "Female": "महिला"}


# ── Font helpers ──────────────────────────────────────────────────────────────

def lf(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_employees(limit=None):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def hindi_name(first, last):
    h_first = HINDI_FIRST.get(first, first)
    h_last  = HINDI_LAST.get(last, last)
    return f"{h_first} {h_last}"


def save_ground_truth(emp):
    eid = emp["employee_id"]
    sides = ["front", "back"]
    source_images = [
        f"{eid}_aadhaar_{side}_{variant}.{VARIANT_EXT[variant]}"
        for side in sides
        for variant in VARIANTS
    ]
    data = {
        "aadhaar_number": emp["aadhaar_number"],
        "name":           f"{emp['first_name']} {emp['last_name']}",
        "date_of_birth":  emp["dob"],
        "gender":         emp["gender"],
        "address":        emp["address"],
        "source_images":  source_images,
    }
    out = GROUND_TRUTH_DIR / f"{eid}_aadhaar.json"
    out.write_text(json.dumps(data, indent=4, ensure_ascii=False))
    return data


# ── Shared card elements ──────────────────────────────────────────────────────

def draw_header(draw, fonts):
    """Tricolor banner with emblem and Aadhaar logo — same on front and back."""
    f_gov_hi, f_gov_en, f_aadhaar = fonts

    # Background of header
    draw.rectangle([0, 0, CARD_W, HEADER_H], fill=BG_COLOR)

    # Tricolor stripes (brushstroke feel — taper at ends)
    stripe_h = 16
    for i, color in enumerate([SAFFRON, "#FFFFFF", INDIA_GREEN]):
        y0 = 20 + i * (stripe_h + 2)
        draw.rounded_rectangle([90, y0, CARD_W - 160, y0 + stripe_h],
                                radius=8, fill=color)

    # "भारत सरकार" on saffron stripe
    draw.text((200, 21), "भारत सरकार", font=f_gov_hi, fill="#7A1010")
    # "Government of India" on green stripe
    draw.text((200, 57), "Government of India", font=f_gov_en, fill="#FFFFFF")

    # Emblem placeholder (left)
    draw.ellipse([8, 6, 84, 82], fill="#FFFFFF", outline="#888888", width=2)
    draw.ellipse([18, 16, 74, 72], outline="#C8A000", width=2)
    draw.text((22, 36), "🏛", font=lf(FONT_REGULAR, 26), fill="#1A3A6C")

    # Aadhaar logo (right) — concentric arcs placeholder
    cx, cy, r = CARD_W - 90, 44, 32
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 fill="#FFFFFF", outline="#C8A000", width=2)
    for rr in [22, 14, 7]:
        draw.arc([cx - rr, cy - rr, cx + rr, cy + rr],
                 start=200, end=340, fill="#1A3A6C", width=3)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill="#1A3A6C")
    draw.text((CARD_W - 120, 68), "आधार", font=f_aadhaar, fill=AADHAAR_RED)

    # Separator line
    draw.line([0, HEADER_H, CARD_W, HEADER_H], fill="#888888", width=1)


def draw_aadhaar_number(draw, number, fonts):
    """Large Aadhaar number band."""
    f_num, f_num_label = fonts
    draw.rectangle([0, NUM_BAND_Y, CARD_W, TAG_BAND_Y], fill=BG_COLOR)
    draw.line([0, NUM_BAND_Y, CARD_W, NUM_BAND_Y], fill="#888888", width=1)
    draw.text((CARD_W // 2, NUM_BAND_Y + 8),  number,
              font=f_num, fill=DARK_TEXT, anchor="mt")


def draw_tagline(draw, fonts):
    """'मेरा आधार, मेरी पहचान' tagline band."""
    f_tag_hi, f_tag_en = fonts
    draw.rectangle([0, TAG_BAND_Y, CARD_W, CARD_H], fill=INDIA_GREEN)
    # Render in parts: "मेरा " black, "आधार," red, " मेरी पहचान" black
    y = TAG_BAND_Y + 18
    x = 160
    draw.text((x, y), "मेरा ", font=f_tag_hi, fill="#FFFFFF")
    w1 = draw.textlength("मेरा ", font=f_tag_hi)
    draw.text((x + w1, y), "आधार,", font=f_tag_hi, fill=SAFFRON)
    w2 = draw.textlength("आधार,", font=f_tag_hi)
    draw.text((x + w1 + w2, y), " मेरी पहचान", font=f_tag_hi, fill="#FFFFFF")


def draw_fake_qr(draw, x, y, size):
    """Fake QR-code pattern with proper corner markers."""
    cell = size // 25
    rng_q = random.Random(9999)

    # Random fill
    for row in range(25):
        for col in range(25):
            c = "#1A1A1A" if rng_q.random() > 0.45 else "#FFFFFF"
            draw.rectangle(
                [x + col * cell, y + row * cell,
                 x + (col + 1) * cell - 1, y + (row + 1) * cell - 1],
                fill=c)

    # Three corner markers (top-left, top-right, bottom-left)
    for ox, oy in [(0, 0), (18, 0), (0, 18)]:
        draw.rectangle([x + ox*cell, y + oy*cell,
                        x + (ox+7)*cell, y + (oy+7)*cell], fill="#1A1A1A")
        draw.rectangle([x + (ox+1)*cell, y + (oy+1)*cell,
                        x + (ox+6)*cell, y + (oy+6)*cell], fill="#FFFFFF")
        draw.rectangle([x + (ox+2)*cell, y + (oy+2)*cell,
                        x + (ox+5)*cell, y + (oy+5)*cell], fill="#1A1A1A")


# ── Card renderers ────────────────────────────────────────────────────────────

def render_front(data, emp):
    img  = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    f_gov_hi  = lf(FONT_DEVA_BOLD, 22)
    f_gov_en  = lf(FONT_BOLD,      20)
    f_aadhaar = lf(FONT_DEVA_BOLD, 18)
    f_name_hi = lf(FONT_DEVA_BOLD, 24)
    f_name_en = lf(FONT_BOLD,      23)
    f_label   = lf(FONT_DEVA,      19)
    f_value   = lf(FONT_BOLD,      20)
    f_num     = lf(FONT_BOLD,      46)
    f_tag_hi  = lf(FONT_DEVA_BOLD, 30)
    f_tiny    = lf(FONT_REGULAR,   15)
    f_dis     = lf(FONT_REGULAR,   13)
    f_dis_hi  = lf(FONT_DEVA,      13)

    draw_header(draw, (f_gov_hi, f_gov_en, f_aadhaar))

    # Photo placeholder
    draw.rounded_rectangle([20, HEADER_H + 12, 200, HEADER_H + 200],
                           radius=4, fill="#A09080", outline="#777777", width=1)
    # Silhouette head
    draw.ellipse([80, HEADER_H + 30, 140, HEADER_H + 90],  fill="#707060")
    draw.ellipse([60, HEADER_H + 90, 160, HEADER_H + 200], fill="#707060")

    # Name (Hindi then English)
    tx, ty = 218, HEADER_H + 14
    h_name = hindi_name(emp["first_name"], emp["last_name"])
    draw.text((tx, ty),      h_name,          font=f_name_hi, fill=DARK_TEXT)
    draw.text((tx, ty + 34), data["name"],     font=f_name_en, fill=DARK_TEXT)

    # DOB
    draw.text((tx, ty + 68),  "जन्म तिथि/DOB:", font=f_label, fill=MUTED_TEXT)
    draw.text((tx, ty + 92),  data["date_of_birth"], font=f_value, fill=DARK_TEXT)

    # Gender
    gender_hi = HINDI_GENDER.get(data["gender"], data["gender"])
    draw.text((tx, ty + 128), "लिंग/Gender:", font=f_label, fill=MUTED_TEXT)
    draw.text((tx, ty + 152), f"{gender_hi}/{data['gender']}", font=f_value, fill=DARK_TEXT)

    # Disclaimer box
    dis_x1, dis_y1, dis_x2, dis_y2 = 218, HEADER_H + 210, CARD_W - 20, NUM_BAND_Y - 10
    draw.rounded_rectangle([dis_x1, dis_y1, dis_x2, dis_y2],
                           radius=4, outline=AADHAAR_RED, width=1, fill="#FFF5F5")
    draw.text((dis_x1 + 8, dis_y1 + 6),
              "आधार पहचान का प्रमाण है, नागरिकता या जन्मतिथि का नहीं।",
              font=f_dis_hi, fill=DARK_TEXT)
    draw.text((dis_x1 + 8, dis_y1 + 28),
              "Aadhaar is proof of identity, not of citizenship or date of birth.",
              font=f_dis, fill=DARK_TEXT)
    draw.text((dis_x1 + 8, dis_y1 + 46),
              "It should be used with verification (Online authentication or",
              font=f_dis, fill=DARK_TEXT)
    draw.text((dis_x1 + 8, dis_y1 + 62),
              "scanning of QR code / Offline XML).",
              font=f_dis, fill=DARK_TEXT)

    draw_aadhaar_number(draw, data["aadhaar_number"], (f_num, f_tiny))
    draw_tagline(draw, (f_tag_hi, f_value))

    return img


def render_back(data, emp):
    img  = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    f_gov_hi  = lf(FONT_DEVA_BOLD, 22)
    f_gov_en  = lf(FONT_BOLD,      20)
    f_aadhaar = lf(FONT_DEVA_BOLD, 18)
    f_label   = lf(FONT_DEVA,      19)
    f_value   = lf(FONT_BOLD,      18)
    f_num     = lf(FONT_BOLD,      46)
    f_tiny    = lf(FONT_REGULAR,   15)
    f_help    = lf(FONT_REGULAR,   16)
    f_tag_hi  = lf(FONT_DEVA_BOLD, 30)

    # Back header (same)
    back_gov_en = lf(FONT_BOLD, 18)
    f_uid_en    = lf(FONT_BOLD, 17)
    draw_header(draw, (f_gov_hi, back_gov_en, f_aadhaar))

    # "Unique Identification Authority of India" below header
    draw.rectangle([0, HEADER_H, CARD_W, HEADER_H + 32], fill=INDIA_GREEN)
    draw.text((CARD_W // 2, HEADER_H + 6),
              "Unique Identification Authority of India",
              font=f_uid_en, fill="#FFFFFF", anchor="mt")

    body_y = HEADER_H + 42
    # Address block (left side)
    draw.text((20, body_y),      "पता:", font=f_label, fill=MUTED_TEXT)
    # Wrap address across lines (~55 chars per line)
    addr = data["address"]
    words = addr.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 52:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))

    ay = body_y + 28
    draw.text((20, ay), "Address:", font=f_label, fill=MUTED_TEXT)
    ay += 24
    for ln in lines[:4]:
        draw.text((20, ay), ln, font=f_value, fill=DARK_TEXT)
        ay += 26

    # QR code (right side)
    qr_size = 220
    qr_x = CARD_W - qr_size - 20
    qr_y = body_y
    draw.rectangle([qr_x - 4, qr_y - 4, qr_x + qr_size + 4, qr_y + qr_size + 4],
                   fill="#FFFFFF", outline="#AAAAAA", width=1)
    draw_fake_qr(draw, qr_x, qr_y, qr_size)

    # Aadhaar fingerprint watermark (bottom-left of back)
    draw.ellipse([20, NUM_BAND_Y - 60, 80, NUM_BAND_Y - 8],
                 outline="#AAAAAA", width=2, fill="#C0AC98")
    for rr in [22, 15, 8]:
        draw.arc([40 - rr, NUM_BAND_Y - 35 - rr, 40 + rr, NUM_BAND_Y - 35 + rr],
                 start=200, end=340, fill="#888888", width=2)

    draw_aadhaar_number(draw, data["aadhaar_number"], (f_num, f_tiny))

    # Helpline band
    draw.rectangle([0, TAG_BAND_Y, CARD_W, CARD_H], fill="#EAD9C5")
    draw.line([0, TAG_BAND_Y, CARD_W, TAG_BAND_Y], fill="#888888", width=1)
    draw.text((30,  TAG_BAND_Y + 20), "☎  1800-300-1947",         font=f_help, fill=DARK_TEXT)
    draw.text((280, TAG_BAND_Y + 20), "✉  help@uidai.gov.in",     font=f_help, fill=DARK_TEXT)
    draw.text((580, TAG_BAND_Y + 20), "🌐  www.uidai.gov.in",     font=f_help, fill=DARK_TEXT)

    return img


# ── Variant transforms (reuse same logic as PAN) ──────────────────────────────

def apply_clean(img, _rng):
    return img.copy(), "png"


def apply_rotated(img, rng):
    angle = rng.uniform(-12, 12)
    return img.rotate(angle, expand=True, fillcolor=(220, 210, 200),
                      resample=Image.BICUBIC), "png"


def apply_blurred(img, rng):
    return img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(1.5, 4.0))), "png"


def apply_compressed(img, rng):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=rng.randint(20, 50))
    buf.seek(0)
    return Image.open(buf).copy(), "jpg"


def _perspective_coeffs(src_quad, dst_quad):
    A, b = [], []
    for (sx, sy), (dx, dy) in zip(src_quad, dst_quad):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        b.append(dx)
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        b.append(dy)
    h = np.linalg.solve(np.array(A, dtype=float), np.array(b, dtype=float))
    return tuple(h)


def _vignette(img, strength):
    arr = np.array(img, dtype=np.float32)
    H, W = arr.shape[:2]
    Y, X = np.ogrid[:H, :W]
    dist = np.sqrt(((X - W/2)/(W/2))**2 + ((Y - H/2)/(H/2))**2)
    mask = np.clip(1 - dist * strength, 0, 1)[:, :, np.newaxis]
    return Image.fromarray(np.clip(arr * mask, 0, 255).astype(np.uint8))


def apply_mobile_photo(img, rng):
    W, H = img.size
    ms = int(min(W, H) * 0.07)
    def s(): return rng.randint(-ms, ms)
    src = [(0,0),(0,H),(W,H),(W,0)]
    dst = [(s(),s()),(s(),H+s()),(W+s(),H+s()),(W+s(),s())]
    coeffs = _perspective_coeffs(src, dst)
    out = img.transform((W, H), Image.PERSPECTIVE, coeffs,
                        resample=Image.BICUBIC, fillcolor=(210, 200, 190))
    out = out.rotate(rng.uniform(-5, 5), expand=False,
                     fillcolor=(210, 200, 190), resample=Image.BICUBIC)
    out = out.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.8, 2.2)))
    out = _vignette(out, rng.uniform(0.4, 0.65))
    sides = rng.sample(["top","bottom","left","right"], k=rng.randint(1, 2))
    l, t, r, b = 0, 0, W, H
    f = rng.uniform(0.04, 0.10)
    for side in sides:
        if side == "top":    t = int(H * f)
        if side == "bottom": b = int(H * (1 - f))
        if side == "left":   l = int(W * f)
        if side == "right":  r = int(W * (1 - f))
    out = out.crop((l, t, r, b))
    buf = io.BytesIO()
    out.convert("RGB").save(buf, format="JPEG", quality=rng.randint(55, 80))
    buf.seek(0)
    return Image.open(buf).copy(), "jpg"


TRANSFORMS = {
    "clean":        apply_clean,
    "rotated":      apply_rotated,
    "blurred":      apply_blurred,
    "compressed":   apply_compressed,
    "mobile_photo": apply_mobile_photo,
}


# ── Main ─────────────────────────────────────────────────────────────────────

def process_employee(emp, rng):
    eid  = emp["employee_id"]
    data = save_ground_truth(emp)

    for side_name, renderer in [("front", render_front), ("back", render_back)]:
        base = renderer(data, emp)
        for variant, transform in TRANSFORMS.items():
            result, ext = transform(base, rng)
            fname = f"{eid}_aadhaar_{side_name}_{variant}.{ext}"
            result.save(GENERATED_DOCS_DIR / fname)
            print(f"  [{side_name:5} | {variant:>12}]  {fname}")


def main(limit=5):
    rng = random.Random(42)
    for emp in load_employees(limit=limit):
        print(f"\n{emp['employee_id']} — {emp['first_name']} {emp['last_name']}")
        process_employee(emp, rng)
    print("\nDone.")


if __name__ == "__main__":
    main()