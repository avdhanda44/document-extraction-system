# Document Extraction POC

This project is a local proof of concept for extracting structured employee form data from uploaded documents.

The main file to run is `main.py`. It reads a file from `uploads/`, extracts text, classifies the document, maps field values, validates the extracted values, and saves the final JSON.

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
- One output JSON file per uploaded file
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
document-extraction-system/
├── Backend/
│   ├── __init__.py
│   ├── main.py
│   ├── json_generator.py
│   ├── processor/
│   │   ├── __init__.py
│   │   ├── text_extractor.py
│   │   ├── pdf_processor.py
│   │   ├── ocr_processor.py
│   │   ├── docx_processor.py
│   ├── extractor/
│   │   ├── __init__.py
│   │   ├── document_classification.py
│   │   ├── field_mapper.py
│   │   ├── validation.py
├── uploads/
├── outputs/
├── main.py
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

Put the document inside the `uploads/` folder.

Run the project from the project root:

```bash
uv --cache-dir .uv-cache run python main.py RahulVerma.pdf
```

Example file names:

```text
AnjaliSharma.pdf
NehaPatil.png
RahulVerma.pdf
```

The output JSON file is saved using this format:

```text
outputs/<input_file_name>_output.json
```

Running the same input file again replaces the same output file.

## Extracted Fields

The employee form schema extracts these fields:

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
- `opencv-python`
- `pdf2image`
- `pillow`
- `python-docx`
- `regex`

If using `uv`, install dependencies with:

```bash
uv sync
```

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

- `extracted_output`
- `validation`

Missing values remain empty strings and are reported through validation errors or warnings rather than being replaced with placeholder text.

## Notes For Contributors

- Put test files in `uploads/`.
- Run `main.py` from the project root.
- Do not manually edit generated JSON files unless testing output formatting.
- If field extraction is wrong, first inspect the raw extracted text from the processor output during debugging.
- If OCR reads a value incorrectly, inspect the image quality and OCR output.
- If a new file type is needed, update `detect_uploaded_file_type()` and `extract_text_by_file_type()` in `Backend/processor/text_extractor.py`.

## Roadmap

Planned next steps:

- Add validation rules for dates, phone numbers, emails, and pincode
- Add confidence scores for OCR fields
- Add a small review/edit interface
- Add Excel support if needed
- Add API support later if needed
