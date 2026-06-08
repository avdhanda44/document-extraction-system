import zipfile
from pathlib import Path

from .docx_processor import extract_text_from_docx
from .ocr_processor import extract_text_from_image
from .pdf_processor import extract_text_from_pdf


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
        return extract_text_from_pdf(file_path)

    if file_type in ["png", "jpg"]:
        return extract_text_from_image(file_path)

    if file_type == "docx":
        return extract_text_from_docx(file_path)

    raise ValueError(f"Unsupported file type: {file_type}")


def extract_uploaded_document(file_name):
    # This is the main function used by main.py.
    # Full flow: find the file, detect its type, extract text, return the result.
    file_path = get_uploaded_file_path(file_name)
    file_type = detect_uploaded_file_type(file_path)
    final_text = extract_text_by_file_type(file_path, file_type)

    return {
        "file_path": file_path,
        "file_type": file_type,
        "is_pdf": file_type == "pdf",
        "final_text": final_text,
    }
