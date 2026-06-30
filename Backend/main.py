from IPython.display import display
import ipywidgets as widgets

from .pipeline import process_uploaded_document


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

            # Run the shared pipeline used by the CLI too.
            process_uploaded_document(file_name)

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
