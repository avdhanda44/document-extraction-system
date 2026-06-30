import json
from datetime import datetime, timezone
from pathlib import Path

from .extractor.document_classification import document_schemas
from .extractor.document_classification import choose_document_type_from_text
from .extractor.field_mapper import extract_field_values_using_schema
from .extractor.validation import validate_extracted_fields
from .json_generator import create_final_json_output, outputs_folder, save_final_json_file
from .processor.text_extractor import extract_uploaded_document


def classify_and_extract_fields(extracted_text):
    classification = choose_document_type_from_text(extracted_text)

    if classification["schema"] is None:
        mapped_fields = {}
    else:
        mapped_fields = extract_field_values_using_schema(
            extracted_text,
            classification["schema"],
        )

    validation = validate_extracted_fields(classification, mapped_fields)

    return classification, mapped_fields, validation


def process_uploaded_document(file_name, save_output=True):
    file_name = file_name.strip()

    if file_name == "":
        raise ValueError("Please enter a file name from the uploads folder.")

    document_result = extract_uploaded_document(file_name)
    classification, mapped_fields, validation = classify_and_extract_fields(
        document_result["final_text"],
    )
    final_json = create_final_json_output(
        document_result,
        classification,
        mapped_fields,
        validation,
    )
    output_path = save_final_json_file(final_json) if save_output else None

    return {
        "document_result": document_result,
        "classification": classification,
        "mapped_fields": mapped_fields,
        "validation": validation,
        "final_json": final_json,
        "output_path": output_path,
    }


def make_classification_for_review(document_type):
    schema = document_schemas.get(document_type)

    return {
        "document_type": document_type,
        "schema": schema,
        "confidence": 1 if schema is not None else 0,
        "confidence_percent": 100 if schema is not None else 0,
        "confidence_level": "high" if schema is not None else "low",
        "matched_fields": list(schema.keys()) if schema is not None else [],
        "missing_fields": [],
        "matched_count": len(schema) if schema is not None else 0,
        "total_fields": len(schema) if schema is not None else 0,
        "all_scores": [],
        "score_gap": 0,
    }


def save_reviewed_document(file_name, file_type, document_type, fields):
    classification = make_classification_for_review(document_type)
    validation = validate_extracted_fields(classification, fields)
    reviewed_folder = outputs_folder / "reviewed"
    reviewed_folder.mkdir(parents=True, exist_ok=True)

    file_stem = Path(file_name).stem
    output_path = reviewed_folder / f"{file_stem}_reviewed.json"
    reviewed_json = {
        "reviewed_output": {
            "file_name": file_name,
            "file_type": file_type,
            "document_type": document_type,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "fields": validation["extracted_data"],
        },
        "validation": {
            "summary": validation["validation_summary"],
            "field_results": validation["validation_results"],
        },
    }

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(reviewed_json, json_file, indent=4, ensure_ascii=False)

    return {
        "reviewed_json": reviewed_json,
        "output_path": output_path,
    }
