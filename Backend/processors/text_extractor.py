import zipfile
from pathlib import Path

from .docx_processor import extract_text_from_docx
from .image_processor import extract_text_from_image, extract_text_from_scanned_pdf
from .pdf_processor import extract_text_from_pdf_with_metadata, extract_text_pages_from_digital_pdf
from ..model_policy import (
    digital_pdf_extractors,
    get_image_ocr_policy,
    get_scanned_pdf_ocr_policy,
)


# Uploaded files will always be kept in the project uploads folder.
project_folder = Path(__file__).resolve().parents[2]
uploads_folder = project_folder / "uploads"

# Put uploaded test files in this folder.
uploads_folder.mkdir(exist_ok=True)


def get_uploaded_file_path(file_name):
    # Clean the file name in case extra spaces were typed.
    file_name = file_name.strip()

    if file_name == "":
        raise ValueError("Please enter a file name.")

    file_path = uploads_folder / file_name

    if not file_path.is_file():
        raise FileNotFoundError(f"File not found in uploads folder: {file_name}")

    return file_path


def detect_uploaded_file_type(file_path):
    # Check file content, not just extension.
    # A file can be named .pdf but still not be a real PDF.
    with open(file_path, "rb") as file:
        file_start = file.read(10)

    if file_start.startswith(b"%PDF"):
        return "pdf"

    if file_start.startswith(b"\x89PNG"):
        return "png"

    if file_start.startswith(b"\xff\xd8"):
        return "jpg"

    # DOCX files are zip files that contain word/document.xml.
    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path) as zipped_file:
            if "word/document.xml" in zipped_file.namelist():
                return "docx"

    return "unknown"


def extract_text_by_file_type(file_path, file_type):
    # Send the file to the correct processor based on its type.
    # Later, if we add Excel or another file type, we add one more condition here.
    if file_type == "pdf":
        return extract_text_from_pdf_with_metadata(file_path)["text"]

    if file_type in ["png", "jpg"]:
        return extract_text_from_image(file_path)

    if file_type == "docx":
        return extract_text_from_docx(file_path)

    raise ValueError(f"Unsupported file type: {file_type}")


def extract_text_with_metadata_by_file_type(file_path, file_type):
    if file_type == "pdf":
        return extract_text_from_pdf_with_metadata(file_path)

    if file_type in ["png", "jpg"]:
        return {
            "text": extract_text_from_image(file_path),
            "engine": "easyocr",
            "method": "image_ocr",
        }

    if file_type == "docx":
        return {
            "text": extract_text_from_docx(file_path),
            "engine": "python-docx",
            "method": "docx_xml_text",
        }

    raise ValueError(f"Unsupported file type: {file_type}")


def make_extraction_candidate(file_path, file_type, text, engine, method):
    return {
        "file_path": file_path,
        "file_type": file_type,
        "is_pdf": file_type == "pdf",
        "final_text": text,
        "extraction_engine": engine,
        "extraction_method": method,
    }


def extract_pdf_candidates(file_path):
    candidates = []

    for extractor_name in digital_pdf_extractors:
        try:
            text_from_pages = extract_text_pages_from_digital_pdf(file_path, extractor_name)
        except Exception:
            continue

        final_text = "\n".join(text_from_pages).strip()

        if final_text:
            candidates.append(
                make_extraction_candidate(
                    file_path,
                    "pdf",
                    final_text,
                    extractor_name,
                    "digital_pdf_text",
                )
            )

    if candidates:
        return candidates

    for model_name in get_scanned_pdf_ocr_policy():
        try:
            final_text = extract_text_from_scanned_pdf(file_path, model_name=model_name)
        except Exception:
            continue

        if final_text:
            candidates.append(
                make_extraction_candidate(
                    file_path,
                    "pdf",
                    final_text,
                    model_name,
                    "scanned_pdf_ocr",
                )
            )

    return candidates


def extract_image_candidates(file_path, file_type):
    candidates = []

    for model_name in get_image_ocr_policy():
        try:
            final_text = extract_text_from_image(file_path, model_name=model_name)
        except Exception:
            continue

        if final_text:
            candidates.append(
                make_extraction_candidate(
                    file_path,
                    file_type,
                    final_text,
                    model_name,
                    "image_ocr",
                )
            )

    return candidates


def extract_document_candidates(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_candidates(file_path)

    if file_type in ["png", "jpg"]:
        return extract_image_candidates(file_path, file_type)

    if file_type == "docx":
        return [
            make_extraction_candidate(
                file_path,
                "docx",
                extract_text_from_docx(file_path),
                "python-docx",
                "docx_xml_text",
            )
        ]

    raise ValueError(f"Unsupported file type: {file_type}")


def extract_uploaded_document(file_name):
    # This is the main function used by main.py.
    # Full flow: find the file, detect its type, extract text, return the result.
    file_path = get_uploaded_file_path(file_name)
    file_type = detect_uploaded_file_type(file_path)
    extraction = extract_text_with_metadata_by_file_type(file_path, file_type)

    return make_extraction_candidate(
        file_path,
        file_type,
        extraction["text"],
        extraction["engine"],
        extraction["method"],
    )


def extract_uploaded_document_candidates(file_name):
    file_path = get_uploaded_file_path(file_name)
    file_type = detect_uploaded_file_type(file_path)
    candidates = extract_document_candidates(file_path, file_type)

    if candidates:
        return candidates

    return [extract_uploaded_document(file_name)]
