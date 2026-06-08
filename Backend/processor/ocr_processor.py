from pathlib import Path
from tempfile import TemporaryDirectory

import easyocr
from pdf2image import convert_from_path


# EasyOCR takes time to start.
# I keep it as None first, then create it once only when OCR is really needed.
ocr_reader = None


def get_easyocr_reader():
    global ocr_reader

    if ocr_reader is None:
        # gpu=False means this will run on a normal CPU.
        ocr_reader = easyocr.Reader(["en"], gpu=False)

    return ocr_reader


def extract_text_from_image(image_path):
    # Use OCR for image files like PNG and JPG.
    reader = get_easyocr_reader()
    detected_text = reader.readtext(str(image_path))

    # EasyOCR gives extra details for each match, but item[1] is the text we need.
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
