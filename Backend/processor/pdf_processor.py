import pdfplumber

from .image_processor import extract_text_from_scanned_pdf


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
