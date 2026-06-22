import pdfplumber

from .image_processor import extract_text_from_scanned_pdf


def get_available_digital_pdf_extractors():
    return ["pdfplumber", "pypdf", "pymupdf", "pdfminer"]


def extract_pages_with_pdfplumber(pdf_path):
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
    extractors = {
        "pdfplumber": extract_pages_with_pdfplumber,
        "pypdf": extract_pages_with_pypdf,
        "pymupdf": extract_pages_with_pymupdf,
        "pdfminer": extract_pages_with_pdfminer,
    }

    if extractor_name not in extractors:
        raise ValueError(f"Unknown digital PDF extractor: {extractor_name}")

    return extractors[extractor_name](pdf_path)


def extract_text_from_pdf(pdf_path):
    # First try normal PDF text extraction.
    # This works for digital PDFs where text can be selected or copied.
    with pdfplumber.open(pdf_path) as pdf:
        text_from_pages = [page.extract_text() or "" for page in pdf.pages]

    final_text = "\n".join(text_from_pages).strip()

    if final_text:
        return final_text

    # If no text was found, the PDF is probably scanned.
    # In that case we load OCR only now, not during normal startup.
    return extract_text_from_scanned_pdf(pdf_path)
