from ..model_policy import digital_pdf_extractors, get_scanned_pdf_ocr_policy
from .image_processor import extract_text_from_scanned_pdf


PDF_EXTRACTORS = {
    "pdfplumber": "extract_pages_with_pdfplumber",
    "pypdf": "extract_pages_with_pypdf",
    "pymupdf": "extract_pages_with_pymupdf",
    "pdfminer": "extract_pages_with_pdfminer",
}


def get_available_digital_pdf_extractors():
    return list(PDF_EXTRACTORS)


def extract_pages_with_pdfplumber(pdf_path):
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return [(page.extract_text() or "").strip() for page in pdf.pages]


def extract_pages_with_pypdf(pdf_path):
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def extract_pages_with_pymupdf(pdf_path):
    import pymupdf

    with pymupdf.open(pdf_path) as document:
        return [(page.get_text("text") or "").strip() for page in document]


def extract_pages_with_pdfminer(pdf_path):
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

    pages = []
    for page_layout in extract_pages(str(pdf_path)):
        text = "\n".join(
            element.get_text().strip()
            for element in page_layout
            if isinstance(element, LTTextContainer) and element.get_text().strip()
        )
        pages.append(text.strip())
    return pages


def extract_text_pages_from_digital_pdf(pdf_path, extractor_name):
    extractor_function_name = PDF_EXTRACTORS.get(extractor_name)

    if extractor_function_name is None:
        raise ValueError(f"Unknown digital PDF extractor: {extractor_name}")

    return globals()[extractor_function_name](pdf_path)


def extract_text_from_pdf_with_metadata(pdf_path):
    for extractor_name in digital_pdf_extractors:
        try:
            text_from_pages = extract_text_pages_from_digital_pdf(pdf_path, extractor_name)
        except Exception:
            continue

        final_text = "\n".join(text_from_pages).strip()

        if final_text:
            return {
                "text": final_text,
                "engine": extractor_name,
                "method": "digital_pdf_text",
            }

    # If no text was found, the PDF is probably scanned.
    # In that case we load OCR only now, not during normal startup.
    for model_name in get_scanned_pdf_ocr_policy():
        try:
            final_text = extract_text_from_scanned_pdf(pdf_path, model_name=model_name)
        except Exception:
            continue

        if final_text:
            return {
                "text": final_text,
                "engine": model_name,
                "method": "scanned_pdf_ocr",
            }

    return {
        "text": extract_text_from_scanned_pdf(pdf_path, model_name="easyocr"),
        "engine": "easyocr",
        "method": "scanned_pdf_ocr",
    }


def extract_text_from_pdf(pdf_path):
    return extract_text_from_pdf_with_metadata(pdf_path)["text"]
