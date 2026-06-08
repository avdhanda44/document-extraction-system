from IPython.display import display
import ipywidgets as widgets

from .extractor.document_classification import choose_document_type_from_text
from .extractor.field_mapper import extract_field_values_using_schema
from .extractor.validation import validate_extracted_fields
from .json_generator import create_final_json_output, save_final_json_file
from .processor.text_extractor import extract_uploaded_document


# Type the exact file name from the uploads folder here.
# Example: RahulVerma.pdf
file_input = widgets.Text(
    placeholder="Example: RahulVerma.pdf",
    description="File:",
)

# This button will start the extraction when we click it.
extract_button = widgets.Button(
    description="Extract",
    button_style="primary",
)

# Messages will be shown here.
output = widgets.Output()


def run_document_processing(button):
    # This function runs when we click the Extract button.
    # It controls the full process from file name to final JSON.

    # Clear old messages first. Success will stay quiet.
    output.clear_output(wait=True)

    # Disable the button while processing so one click cannot run twice.
    extract_button.disabled = True

    try:
        with output:
            # Get the file name from the text box and remove extra spaces.
            file_name = file_input.value.strip()

            # If no file name is typed, stop here and ask for one.
            if file_name == "":
                print("Please enter a file name from the uploads folder.")
                return

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
        with output:
            # Show only errors, because successful runs should stay quiet.
            print(error)
    finally:
        extract_button.disabled = False


# Clear old button clicks first.
# This stops the extraction from running multiple times if we rerun this cell.
try:
    extract_button._click_handlers.callbacks = []
except Exception:
    pass

# Connect the button to the function above.
# After this line, clicking Extract will run run_document_processing().
extract_button.on_click(run_document_processing)

# Display the button only after it is connected.
# This avoids showing an old button that does not run anything.
display(file_input, extract_button, output)
