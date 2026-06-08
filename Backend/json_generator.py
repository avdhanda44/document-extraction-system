import json
from pathlib import Path


def find_outputs_folder_for_json_files():
    # VS Code may run the file from Backend or from the project folder.
    # This keeps JSON files saved in the project-level outputs folder.
    current_folder = Path.cwd()

    if (current_folder / "outputs").exists():
        return current_folder / "outputs"

    if (current_folder.parent / "outputs").exists():
        return current_folder.parent / "outputs"

    return current_folder / "outputs"


outputs_folder = find_outputs_folder_for_json_files()
outputs_folder.mkdir(exist_ok=True)


def create_final_json_output(document_result, classification, mapped_fields, validation):
    # This creates the final JSON in the format we want to save.
    # First we keep extracted output, then we keep validation details.
    return {
        "extracted_output": {
            "file_name": document_result["file_path"].name,
            "file_type": document_result["file_type"],
            "document_type": classification["document_type"],
            "confidence_percent": classification["confidence_percent"],
            "confidence_level": classification["confidence_level"],
            "fields": validation["extracted_data"],
        },
        "validation": {
            "summary": validation["validation_summary"],
            "field_results": validation["validation_results"],
        },
    }


def save_final_json_file(final_json):
    # Save one output file per uploaded document.
    # If we run the same file again, this will replace the old output for that file.
    file_stem = Path(final_json["extracted_output"]["file_name"]).stem
    output_path = outputs_folder / f"{file_stem}_output.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_json, json_file, indent=4, ensure_ascii=False)

    return output_path
