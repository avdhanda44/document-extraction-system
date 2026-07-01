import json
from datetime import datetime, timezone
from pathlib import Path

from .extractors.document_classification import document_schemas
from .extractors.document_classification import choose_document_type_from_text
from .extractors.field_mapper import extract_field_values_using_schema
from .extractors.validation import validate_extracted_fields
from .output import create_final_json_output
from .model_policy import get_document_engine_preference
from .processors.text_extractor import extract_uploaded_document_candidates


project_folder = Path(__file__).resolve().parent.parent
website_output_folder = project_folder / "outputs"
website_output_folder.mkdir(exist_ok=True)


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

    extraction_candidates = extract_uploaded_document_candidates(file_name)
    candidate_results = []

    for document_result in extraction_candidates:
        classification, mapped_fields, validation = classify_and_extract_fields(
            document_result["final_text"],
        )
        candidate_results.append(
            {
                "document_result": document_result,
                "classification": classification,
                "mapped_fields": mapped_fields,
                "validation": validation,
                "score": score_extraction_candidate(
                    document_result,
                    classification,
                    mapped_fields,
                    validation,
                ),
            }
        )

    best_candidate = max(candidate_results, key=lambda candidate: candidate["score"])
    document_result = best_candidate["document_result"]
    classification = best_candidate["classification"]
    mapped_fields = best_candidate["mapped_fields"]
    validation = best_candidate["validation"]
    document_result["attempts"] = [
        {
            "engine": candidate["document_result"]["extraction_engine"],
            "method": candidate["document_result"]["extraction_method"],
            "document_type": candidate["classification"]["document_type"],
            "confidence_percent": candidate["classification"]["confidence_percent"],
            "valid_fields": candidate["validation"]["validation_summary"]["valid_fields"],
            "invalid_fields": candidate["validation"]["validation_summary"]["invalid_fields"],
            "fields_with_warnings": candidate["validation"]["validation_summary"]["fields_with_warnings"],
        }
        for candidate in candidate_results
    ]

    final_json = create_final_json_output(
        document_result,
        classification,
        mapped_fields,
        validation,
    )
    output_path = save_website_json_file(final_json) if save_output else None

    return {
        "document_result": document_result,
        "classification": classification,
        "mapped_fields": mapped_fields,
        "validation": validation,
        "final_json": final_json,
        "output_path": output_path,
    }


def score_extraction_candidate(document_result, classification, mapped_fields, validation):
    validation_summary = validation["validation_summary"]
    filled_field_count = sum(1 for value in mapped_fields.values() if has_field_value(value))
    engine_preference = get_document_engine_preference(
        classification["document_type"],
        document_result["extraction_engine"],
    )

    return (
        classification["schema"] is not None,
        validation_summary["ready_to_save"],
        validation_summary["valid_fields"],
        -validation_summary["invalid_fields"],
        -validation_summary["fields_with_warnings"],
        classification["confidence_percent"],
        engine_preference,
        filled_field_count,
    )


def has_field_value(value):
    if value is None:
        return False

    if isinstance(value, str):
        return value.strip() != ""

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0

    return True


def save_website_json_file(final_json):
    file_stem = Path(final_json["extracted_output"]["file_name"]).stem
    output_path = website_output_folder / f"{file_stem}_output.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_json, json_file, indent=4, ensure_ascii=False)

    return output_path


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

    file_stem = Path(file_name).stem
    output_path = website_output_folder / f"{file_stem}_reviewed.json"
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
