import re
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline import process_uploaded_document, save_reviewed_document
from .processor.text_extractor import uploads_folder


allowed_file_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}

app = FastAPI(title="Document Extraction Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewedDocumentRequest(BaseModel):
    file_name: str
    file_type: str
    document_type: str
    fields: dict[str, str | bool | list[str] | None] = Field(default_factory=dict)


def make_safe_file_name(file_name):
    clean_name = Path(file_name or "uploaded_document").name.strip()
    clean_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", clean_name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()

    if clean_name in {"", ".", ".."}:
        clean_name = "uploaded_document"

    return clean_name


def make_unique_upload_path(file_name):
    safe_name = make_safe_file_name(file_name)
    upload_path = uploads_folder / safe_name

    if not upload_path.exists():
        return upload_path

    stem = upload_path.stem
    suffix = upload_path.suffix

    for index in range(1, 1000):
        candidate = uploads_folder / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise HTTPException(status_code=409, detail="Could not create a unique upload file name.")


def make_extract_response(result):
    extracted_output = result["final_json"]["extracted_output"]
    validation = result["final_json"]["validation"]

    return {
        "file_name": extracted_output["file_name"],
        "file_type": extracted_output["file_type"],
        "document_type": extracted_output["document_type"],
        "confidence_percent": extracted_output["confidence_percent"],
        "confidence_level": extracted_output["confidence_level"],
        "fields": extracted_output["fields"],
        "validation": validation,
        "raw_text": result["document_result"].get("final_text", ""),
        "extraction_engine": result["document_result"].get("extraction_engine", "unknown"),
        "extraction_method": result["document_result"].get("extraction_method", "unknown"),
        "uploaded_file_deleted": result["document_result"].get("uploaded_file_deleted", False),
        "output_path": str(result["output_path"]) if result["output_path"] else "",
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/extract")
def extract_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in allowed_file_extensions:
        allowed = ", ".join(sorted(allowed_file_extensions))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Use one of: {allowed}")

    upload_path = make_unique_upload_path(file.filename or "uploaded_document")
    uploaded_file_deleted = False

    try:
        with upload_path.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)

        result = process_uploaded_document(upload_path.name)
        try:
            upload_path.unlink()
            uploaded_file_deleted = True
        except FileNotFoundError:
            uploaded_file_deleted = True
        result["document_result"]["uploaded_file_deleted"] = uploaded_file_deleted
        return make_extract_response(result)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        if upload_path.exists() and not uploaded_file_deleted:
            upload_path.unlink()
        file.file.close()


@app.post("/api/reviewed")
def save_reviewed(request: ReviewedDocumentRequest):
    try:
        result = save_reviewed_document(
            request.file_name,
            request.file_type,
            request.document_type,
            request.fields,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "message": "Reviewed JSON saved.",
        "output_path": str(result["output_path"]),
        "reviewed_output": result["reviewed_json"]["reviewed_output"],
        "validation": result["reviewed_json"]["validation"],
    }
