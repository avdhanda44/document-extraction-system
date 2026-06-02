# Document Extraction POC

This project is a local proof of concept for extracting structured employee form data from uploaded documents.

The main file to run is `notebooks/document_extraction_poc.ipynb`. It loads a few helper Python files, asks for a file from `uploads/`, extracts the text, converts the form fields into JSON, and saves the result in `outputs/`.

The helper Python files are available in the `notebooks/` folder as `01_project_setup.py`, `02_text_extraction.py`, `03_field_extraction.py`, `04_save_output.py`, and `05_validation.py`.

## Current Status

Implemented:

- File name validation against the local `uploads/` folder
- File type detection using file content, not only file extension
- Digital PDF text extraction with `pdfplumber`
- Scanned PDF OCR using `pdf2image` and `EasyOCR`
- PNG/JPG image OCR using `EasyOCR`
- DOCX text extraction using `python-docx`
- Schema-based extraction for employee enrollment forms
- Cleanup for common OCR email mistakes
- Timestamped JSON output files

- Post-extraction validation layer
- Email validation
- Mobile number validation
- Pincode validation
- Date validation
- Employee ID validation
- Required field validation
- Validation summary generation

Not implemented yet:

- Excel extraction
- API or web app
- Human review/edit screen
- Database storage

## Project Structure

```text
document_extractor/
├── notebooks/
│   ├── document_extraction_poc.ipynb   # main notebook to run
│   ├── 01_project_setup.py             # python helper code for project setup
│   ├── 02_text_extraction.py           # python helper code for text extraction
│   ├── 03_field_extraction.py          # python helper code for field extraction
│   ├── 04_save_output.py               # python helper code for output saving
│   ├── 05_validation.py                # python helper code for validation helpers
├── uploads/                        # input files
├── outputs/                        # generated JSON files
├── pyproject.toml
├── uv.lock
└── README.md
```

## Supported Input Files

Currently supported:

- `.pdf` files with machine-readable text
- scanned `.pdf` files, if Poppler is installed
- `.png` images
- `.jpg` / `.jpeg` images
- `.docx` Word documents

Scanned PDFs are converted to images with `pdf2image`, then read with `EasyOCR`.

DOCX files are read directly with `python-docx`. The extractor reads both normal paragraphs and table cells.

## How To Run

Open `notebooks/document_extraction_poc.ipynb` in VS Code or Jupyter and run the cells from top to bottom.

The first code cell loads the helper Python files from the `notebooks/` folder:

```python
%run './notebooks/01_project_setup.py'
%run './notebooks/02_text_extraction.py'
%run './notebooks/03_field_extraction.py'
%run './notebooks/04_save_output.py'
%run './notebooks/05_validation.py'
```

Python module equivalents of the helper notebooks are also available in the same folder if you want a script-friendly version of the helper logic.

After that, the main notebook runs the POC flow:

1. Enter a file name from `uploads/`.
2. Validate the selected file.
3. Detect whether the file is PDF, image, or DOCX.
4. Extract raw text.
5. Convert the text into structured JSON.
6. Save the JSON file in `outputs/`.

Example file names:

```text
AnjaliSharma.pdf
NehaPatil.png
EmployeeForm.docx
```

The output JSON file is saved using this format:

```text
<input_file_name>_<YYYYMMDD_HHMMSS>.json
```

## Extracted Fields

The notebook extracts these fields:

```json
{
    "employee_name": "",
    "employee_id": "",
    "date_of_birth": "",
    "date_of_joining": "",
    "department": "",
    "designation": "",
    "mobile_number": "",
    "email": "",
    "address": "",
    "pincode": ""
}
```

The field mapping is controlled by `form_schema` in `notebooks/01_project_setup.py`.

## Notebook Guide

`notebooks/document_extraction_poc.ipynb` is the only notebook you need to run manually.

The helper Python files keep the code organized:

- `notebooks/01_project_setup.py`: shared imports, folders, form schema, and file validation
- `notebooks/02_text_extraction.py`: file type detection and raw text extraction
- `notebooks/03_field_extraction.py`: OCR cleanup, label matching, and field extraction
- `notebooks/04_save_output.py`: timestamped JSON saving
- `notebooks/05_validation.py`: validation helpers

This keeps the project notebook-based, but avoids putting all code in one large notebook.

## Extraction Logic

The parser handles common form layouts:

- label and value on the same line
- label on one line and value on the next line
- separator-only values such as `:` or `-`
- OCR-split labels, such as `Date of` followed by `Joining:`
- common email OCR issues, such as spaces or colons inside the local part

Example cleanup:

```text
priyanka nair@example.com -> priyanka.nair@example.com
neha:patil@example.com    -> neha.patil@example.com
```

## Dependencies

Defined in `pyproject.toml`:

- Python `>=3.12`
- `easyocr`
- `pdfplumber`
- `ipywidgets`
- `ipykernel`
- `opencv-python`
- `pdf2image`
- `pillow`
- `python-docx`
- `nbformat`

If using `uv`, install dependencies with:

```bash
uv sync
```

Then open the notebook using the project virtual environment.

Note: scanned PDF OCR requires Poppler because `pdf2image` depends on it.

## Validation Layer

After field extraction, the extracted JSON is validated before being saved.

Validation checks:

- Required fields
- Email format
- Mobile number format
- Pincode format
- Date validity
- Employee ID format

The final output contains:

- extracted_data
- validation_results
- validation_summary

Missing values remain empty strings and are reported through validation errors or warnings rather than being replaced with placeholder text.

## Notes For Contributors

- Put test files in `uploads/`.
- Run `notebooks/document_extraction_poc.ipynb` from top to bottom.
- Do not manually edit generated JSON files unless testing output formatting.
- If field extraction is wrong, first inspect the raw text output cell.
- If OCR reads a value incorrectly, improve cleanup in `notebooks/03_field_extraction.py`.
- If a new field is needed, add it to `form_schema` in `notebooks/01_project_setup.py`.
- If a new file type is needed, update `detect_file_type()` and `extract_text()` in `notebooks/02_text_extraction.py`.

## Roadmap

Planned next steps:

- Add validation rules for dates, phone numbers, emails, and pincode
- Add confidence scores for OCR fields
- Add a small review/edit interface
- Add Excel support if needed
- Add API support later if the POC moves beyond notebooks
