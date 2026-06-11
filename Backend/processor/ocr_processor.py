import os
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory

import easyocr
from pdf2image import convert_from_path
from PIL import Image

# Maximum image side length fed to PaddleOCR — prevents OOM on large scans.
_PADDLE_MAX_SIDE = 1500

# Lazy singletons — loaded once on first use.
_easyocr_reader = None
_paddle_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)
    return _easyocr_reader


def _get_paddle_reader():
    global _paddle_reader
    if _paddle_reader is None:
        from paddleocr import PaddleOCR
        # Disable heavy preprocessing models to save memory.
        _paddle_reader = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
    return _paddle_reader


# Keep the old name so existing code that imports it still works.
def get_easyocr_reader():
    return _get_easyocr_reader()


def _resize_for_paddle(image_path: str) -> str:
    """
    If the image is larger than _PADDLE_MAX_SIDE on any dimension, downscale it
    and write to a temp file. Returns the (possibly new) path to use.
    """
    img = Image.open(image_path)
    w, h = img.size
    if max(w, h) <= _PADDLE_MAX_SIDE:
        return image_path
    ratio = _PADDLE_MAX_SIDE / max(w, h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def extract_text_from_image(image_path):
    engine = os.getenv("OCR_ENGINE", "easyocr").lower()

    if engine == "paddleocr":
        resized_path = _resize_for_paddle(str(image_path))
        reader = _get_paddle_reader()
        result = reader.ocr(resized_path)
        if resized_path != str(image_path):
            os.unlink(resized_path)
        lines = []
        if result:
            for page in result:
                if isinstance(page, dict):
                    lines.extend(page.get("rec_texts", []))
                elif isinstance(page, list):
                    for line in page:
                        if line and len(line) >= 2:
                            lines.append(line[1][0])
        return "\n".join(lines).strip()

    if engine == "tesseract":
        import pytesseract
        img = Image.open(str(image_path))
        # eng+hin covers English and Devanagari (Hindi) on the same card
        text = pytesseract.image_to_string(img, lang="eng+hin", config="--psm 3")
        return text.strip()

    # Default: EasyOCR
    reader = _get_easyocr_reader()
    detected_text = reader.readtext(str(image_path))
    return "\n".join(item[1] for item in detected_text).strip()


def extract_text_from_scanned_pdf(pdf_path):
    # Scanned PDFs are basically images inside a PDF.
    # So first we convert each page into an image, then run OCR on those images.
    try:
        pages = convert_from_path(str(pdf_path), dpi=350)
    except Exception as error:
        raise RuntimeError("Scanned PDF files need Poppler installed.") from error

    text_from_pages = []

    with TemporaryDirectory() as temporary_folder:
        temporary_folder = Path(temporary_folder)

        for page_number, page in enumerate(pages, start=1):
            image_path = temporary_folder / f"page_{page_number}.png"
            page.save(image_path, "PNG")
            text_from_pages.append(extract_text_from_image(image_path))

    final_text = "\n".join(text_from_pages).strip()

    if final_text == "":
        raise ValueError("No readable text found in scanned PDF.")

    return final_text