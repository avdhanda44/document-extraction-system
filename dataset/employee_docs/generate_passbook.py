"""
Bank passbook front-page generator — five variants per employee.

Output:
  generated_docs/passbook/  EMP001_passbook_clean.png
                            EMP001_passbook_rotated.png
                            EMP001_passbook_blurred.png
                            EMP001_passbook_compressed.jpg
                            EMP001_passbook_mobile_photo.jpg

Ground truth:
  ground_truth/passbook/    EMP001_passbook.json
"""

import csv
import io
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR         = Path(__file__).parent
CSV_PATH         = BASE_DIR / "employees.csv"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth" / "passbook"
GENERATED_DIR    = BASE_DIR / "generated_docs" / "passbook"

for d in [GROUND_TRUTH_DIR, GENERATED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FONT_REGULAR = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD    = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_MONO    = "/System/Library/Fonts/Courier.ttc"
FONT_DEVA    = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"
FONT_DEVA_BD = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"

DOC_W, DOC_H = 1200, 820

VARIANTS = ["clean", "rotated", "blurred", "compressed", "mobile_photo"]
VARIANT_EXT = {
    "clean":        "png",
    "rotated":      "png",
    "blurred":      "png",
    "compressed":   "jpg",
    "mobile_photo": "jpg",
}

BANK_STYLES = {
    "State Bank of India":    {"color": "#1A4CA1", "abbr": "SBI",   "hindi": "भारतीय स्टेट बैंक"},
    "HDFC Bank":              {"color": "#004C8F", "abbr": "HDFC",  "hindi": "एचडीएफसी बैंक"},
    "ICICI Bank":             {"color": "#B02A1A", "abbr": "ICICI", "hindi": "आईसीआईसीआई बैंक"},
    "Punjab National Bank":   {"color": "#5B2D8E", "abbr": "PNB",  "hindi": "पंजाब नेशनल बैंक"},
    "Karnataka Bank":         {"color": "#C8282A", "abbr": "KBL",  "hindi": "कर्नाटक बैंक"},
    "Axis Bank":              {"color": "#97144D", "abbr": "AXIS",  "hindi": "एक्सिस बैंक"},
    "Andhra Bank":            {"color": "#D44000", "abbr": "AB",    "hindi": "आंध्रा बैंक"},
    "Federal Bank":           {"color": "#005596", "abbr": "FB",    "hindi": "फेडरल बैंक"},
    "Bank of India":          {"color": "#CC0000", "abbr": "BOI",   "hindi": "बैंक ऑफ इंडिया"},
    "Central Bank of India":  {"color": "#8B0000", "abbr": "CBI",   "hindi": "सेंट्रल बैंक ऑफ इंडिया"},
}

TITLE_PREFIX = {"Male": "Mr.", "Female": "Ms."}
SDH_PREFIX   = {"Male": "S/O", "Female": "D/O"}


# ── Font helper ───────────────────────────────────────────────────────────────

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


def derive_fields(emp):
    """Generate fields not present in CSV."""
    num = int(emp["employee_id"].replace("EMP", ""))
    cif_number   = f"{90700000 + num * 29261:09d}"
    nom_reg_no   = f"{num * 3248:011d}"

    # Account opening date — 3 years after DOB year
    dob_parts = emp["dob"].split("/")
    open_year = int(dob_parts[2]) + 22        # rough working-age offset
    acct_open = f"{dob_parts[0]}/{dob_parts[1]}/{open_year}"
    issue_date = f"{dob_parts[0]}/{dob_parts[1]}/{open_year}"

    # Branch email and phone from IFSC
    ifsc   = emp["ifsc"].lower()
    email  = f"{ifsc[:4]}.{emp['ifsc'][4:]}@{ifsc[:4]}.co.in"
    phone  = f"0{num * 256165 % 9000000 + 1000000}"
    micr   = f"{num * 768002556 % 900000000 + 100000000}"
    code   = f"{10000 + num * 255}"

    return {
        "cif_number":   cif_number,
        "nom_reg_no":   nom_reg_no,
        "acct_open":    acct_open,
        "issue_date":   issue_date,
        "email":        email,
        "phone":        phone,
        "micr":         str(micr),
        "branch_code":  str(code),
    }


def save_ground_truth(emp, extra):
    eid = emp["employee_id"]
    data = {
        "bank_name":      emp["bank_name"],
        "branch_name":    emp["branch_name"],
        "ifsc":           emp["ifsc"],
        "account_number": emp["account_number"],
        "account_type":   "REGULAR SAVINGS BANK ACCOUNT",
        "account_holder": f"{TITLE_PREFIX[emp['gender']]} {emp['first_name']} {emp['last_name']}",
        "father_name":    emp["father_name"],
        "cif_number":     extra["cif_number"],
        "pan_number":     emp["pan_number"],
        "address":        emp["address"],
        "account_opened": extra["acct_open"],
        "source_images": [
            f"{eid}_passbook_{variant}.{VARIANT_EXT[variant]}"
            for variant in VARIANTS
        ],
    }
    out = GROUND_TRUTH_DIR / f"{eid}_passbook.json"
    out.write_text(json.dumps(data, indent=4, ensure_ascii=False))
    return data


# ── Passbook renderer ─────────────────────────────────────────────────────────

def draw_ruled_lines(draw, y_start, y_end, step=28):
    """Faint horizontal ruled lines like a passbook page."""
    y = y_start
    while y < y_end:
        draw.line([0, y, DOC_W, y], fill="#DDDDDD", width=1)
        y += step


def draw_stamp(draw, cx, cy, radius):
    """Circular branch manager stamp (purple ink)."""
    stamp_color = "#5B2A8A"
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                 outline=stamp_color, width=3)
    draw.ellipse([cx - radius + 6, cy - radius + 6,
                  cx + radius - 6, cy + radius - 6],
                 outline=stamp_color, width=1)
    f_stamp_hi = lf(FONT_DEVA,    16)
    f_stamp_en = lf(FONT_REGULAR, 15)
    draw.text((cx, cy - 14), "शाखा प्रबंधक", font=f_stamp_hi,
              fill=stamp_color, anchor="mm")
    draw.text((cx, cy + 10), "Branch Manager", font=f_stamp_en,
              fill=stamp_color, anchor="mm")


def render_passbook(data, emp, extra):
    style = BANK_STYLES.get(emp["bank_name"],
                             {"color": "#333333", "abbr": "BNK", "hindi": emp["bank_name"]})
    bank_color = style["color"]

    img  = Image.new("RGB", (DOC_W, DOC_H), "#FAFAF8")
    draw = ImageDraw.Draw(img)

    # Ruled lines (background texture)
    draw_ruled_lines(draw, 170, DOC_H - 60)

    # ── Top color band ────────────────────────────────────────────
    draw.rectangle([0, 0, DOC_W, 8], fill=bank_color)

    # ── Bank name (Hindi) — left ──────────────────────────────────
    f_bank_hi = lf(FONT_DEVA_BD, 30)
    f_bank_en = lf(FONT_BOLD,    28)
    draw.text((30, 20), style["hindi"], font=f_bank_hi, fill=bank_color)

    # ── Bank logo — right ─────────────────────────────────────────
    lx, ly, lr = DOC_W - 70, 60, 44
    draw.ellipse([lx - lr, ly - lr, lx + lr, ly + lr],
                 fill=bank_color, outline="#AAAAAA", width=1)
    f_abbr = lf(FONT_BOLD, 18 if len(style["abbr"]) <= 3 else 14)
    draw.text((lx, ly), style["abbr"], font=f_abbr, fill="#FFFFFF", anchor="mm")
    draw.text((DOC_W - 180, 20), emp["bank_name"], font=f_bank_en, fill=bank_color)

    # ── Branch details — centre ───────────────────────────────────
    f_branch = lf(FONT_BOLD,    16)
    f_detail = lf(FONT_REGULAR, 15)
    bx = 340
    draw.text((bx, 18), f"Branch: {emp['branch_name'].upper()}",
              font=f_branch, fill="#1A1A1A")
    draw.text((bx + 340, 18), f"Code: {extra['branch_code']}",
              font=f_detail, fill="#1A1A1A")
    draw.text((bx, 40), f"Email: {extra['email']}",
              font=f_detail, fill="#1A1A1A")
    draw.text((bx + 340, 40), f"Buss. Hrs: 10:00-16:00",
              font=f_detail, fill="#1A1A1A")
    draw.text((bx, 62), f"Phone No.: {extra['phone']}",
              font=f_detail, fill="#1A1A1A")
    draw.text((bx + 340, 62), f"MICR: {extra['micr']}",
              font=f_detail, fill="#1A1A1A")
    draw.text((bx, 84), f"IFSC: {emp['ifsc']}",
              font=f_detail, fill="#1A1A1A")

    # ── Divider ───────────────────────────────────────────────────
    draw.line([0, 115, DOC_W, 115], fill="#AAAAAA", width=1)
    draw.line([0, 117, DOC_W, 117], fill=bank_color, width=2)

    # ── Customer details — monospace feel ─────────────────────────
    f_label = lf(FONT_MONO, 17)
    f_value = lf(FONT_MONO, 17)
    f_bold  = lf(FONT_BOLD,  17)

    lx, rx = 30, 620
    y = 138

    def row(label, value, x=lx, bold_val=False):
        nonlocal y
        draw.text((x, y), label, font=f_label, fill="#333333")
        vfont = f_bold if bold_val else f_value
        draw.text((x + 220, y), value, font=vfont, fill="#1A1A1A")
        y += 34

    title  = TITLE_PREFIX.get(emp["gender"], "")
    sdh    = SDH_PREFIX.get(emp["gender"], "S/O")
    name   = f"{title} {emp['first_name']} {emp['last_name']}"

    row("Name          :", name, bold_val=True)
    row(f"{'S/D/H/o':<14}:", emp["father_name"].upper())
    row("CIF Number    :", extra["cif_number"])
    row("Account No.   :", emp["account_number"], bold_val=True)
    row("A/c Type      :", "REGULAR SAVINGS BANK ACCOUNT")

    # Address (may be long — wrap manually)
    addr_words = emp["address"].split()
    lines, line = [], []
    for w in addr_words:
        line.append(w)
        if len(" ".join(line)) > 40:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))

    draw.text((lx, y), "Address       :", font=f_label, fill="#333333")
    draw.text((lx + 220, y), lines[0] if lines else "", font=f_value, fill="#1A1A1A")
    for ln in lines[1:]:
        y += 28
        draw.text((lx + 220, y), ln, font=f_value, fill="#1A1A1A")
    y += 34

    # ── Right column ──────────────────────────────────────────────
    ry = 138
    def rrow(label, value):
        nonlocal ry
        draw.text((rx, ry), label, font=f_label, fill="#333333")
        draw.text((rx + 230, ry), value, font=f_value, fill="#1A1A1A")
        ry += 34

    rrow("MOP           :", "SINGLE")
    rrow("A/c Opening Dt:", extra["acct_open"])
    rrow("Nom Reg No    :", extra["nom_reg_no"])
    rrow("Customer's PAN:", emp["pan_number"])
    rrow("Date of Issue :", extra["issue_date"])
    draw.text((rx, ry), "CONTINUATION", font=f_bold, fill=bank_color)

    # ── Vertical divider between columns ─────────────────────────
    draw.line([rx - 20, 115, rx - 20, DOC_H - 80], fill="#CCCCCC", width=1)

    # ── Branch manager stamp ──────────────────────────────────────
    draw_stamp(draw, DOC_W - 120, DOC_H - 120, 80)

    # ── Bottom band ───────────────────────────────────────────────
    draw.rectangle([0, DOC_H - 8, DOC_W, DOC_H], fill=bank_color)

    return img


# ── Variant transforms ────────────────────────────────────────────────────────

def apply_clean(img, _rng):
    return img.copy(), "png"


def apply_rotated(img, rng):
    angle = rng.uniform(-8, 8)
    return img.rotate(angle, expand=True, fillcolor=(240, 240, 238),
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
    ms = int(min(W, H) * 0.06)
    def s(): return rng.randint(-ms, ms)
    src = [(0,0),(0,H),(W,H),(W,0)]
    dst = [(s(),s()),(s(),H+s()),(W+s(),H+s()),(W+s(),s())]
    coeffs = _perspective_coeffs(src, dst)
    out = img.transform((W, H), Image.PERSPECTIVE, coeffs,
                        resample=Image.BICUBIC, fillcolor=(235, 235, 232))
    out = out.rotate(rng.uniform(-4, 4), expand=False,
                     fillcolor=(235, 235, 232), resample=Image.BICUBIC)
    out = out.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.8, 2.0)))
    out = _vignette(out, rng.uniform(0.35, 0.60))
    sides = rng.sample(["top","bottom","left","right"], k=rng.randint(1, 2))
    l, t, r, b = 0, 0, W, H
    f = rng.uniform(0.03, 0.09)
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
    eid   = emp["employee_id"]
    extra = derive_fields(emp)
    data  = save_ground_truth(emp, extra)
    base  = render_passbook(data, emp, extra)

    for variant, transform in TRANSFORMS.items():
        result, ext = transform(base, rng)
        fname = f"{eid}_passbook_{variant}.{ext}"
        result.save(GENERATED_DIR / fname)
        print(f"  [{variant:>12}]  {fname}")


def main(limit=5):
    rng = random.Random(42)
    for emp in load_employees(limit=limit):
        print(f"\n{emp['employee_id']} — {emp['first_name']} {emp['last_name']} ({emp['bank_name']})")
        process_employee(emp, rng)
    print("\nDone.")


if __name__ == "__main__":
    main()