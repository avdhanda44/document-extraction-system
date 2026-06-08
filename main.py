import sys

from Backend.extractor.document_classification import choose_document_type_from_text
from Backend.extractor.field_mapper import extract_field_values_using_schema
from Backend.extractor.validation import validate_extracted_fields
from Backend.json_generator import create_final_json_output, save_final_json_file
from Backend.processor.text_extractor import extract_uploaded_document


def run_document_processing(file_name):
    # This function controls the full process from file name to final JSON.

    # Get the file name and remove extra spaces.
    file_name = file_name.strip()

    # If no file name is typed, stop here and ask for one.
    if file_name == "":
        print("Please enter a file name from the uploads folder.")
        return

    try:
        # Step 1: read the uploaded document and get raw text.
        result = extract_uploaded_document(file_name)

        # Step 2: use the raw text to decide which schema fits best.
        classification = choose_document_type_from_text(result["final_text"])

        # Step 3: if we know the schema, extract values for each field.
        if classification["schema"] is not None:
            mapped_fields = extract_field_values_using_schema(result["final_text"], classification["schema"])
        else:
            mapped_fields = {}

        # Step 4: validate the mapped fields before saving.
        validation = validate_extracted_fields(classification, mapped_fields)

        # Step 5: create the final JSON and save it in outputs.
        final_json = create_final_json_output(result, classification, mapped_fields, validation)
        save_final_json_file(final_json)

        # Show one short success message, but do not print the full JSON.
        print("Done. File processed and saved in the outputs folder.")
    except Exception as error:
        # Show a simple error message so the output is easier to read.
        print(error)


def main():
    if len(sys.argv) < 2:
        print("Please enter a file name from the uploads folder.")
        return

    run_document_processing(sys.argv[1])


if __name__ == "__main__":
    main()
