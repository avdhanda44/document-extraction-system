# Document Extraction POC

This project is a local proof of concept for extracting structured data from employee documents and generated identity/banking/invoice samples.

The main file to run is `main.py`. It reads a file from `uploads/`, extracts text, classifies the document, maps field values, validates the extracted values, and saves the final JSON.

## Current Status

Implemented:

- File name validation against the local `uploads/` folder
- File type detection using file content, not only file extension
- Digital PDF text extraction with `pdfplumber`
- Scanned PDF OCR using `pdf2image` and OCR engines
- PNG/JPG image OCR using available OCR engines
- DOCX text extraction using `python-docx`
- Schema-based extraction for employee enrollment forms
- Schema-based extraction for Aadhaar, PAN, passbook, and invoice documents
- Batch evaluation for generated Aadhaar, PAN, passbook, and invoice images
- JSON output per processed image
- Excel accuracy reports for batch evaluation
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
│   │   ├── image_processor.py
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

Scanned PDFs are converted to images with `pdf2image`, then read with the OCR processor. EasyOCR is the default OCR engine.

DOCX files are read directly with `python-docx`. The extractor reads both normal paragraphs and table cells.

## How To Run

Change into the project folder:

```bash
cd "/Users/anuradhakumari/Library/Mobile Documents/com~apple~CloudDocs/KAINest/document-extraction-system"
```

Activate the local virtual environment if you want to run commands inside it:

```bash
source .venv/bin/activate
```

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

The output JSON file is saved by document type and input format:

```text
outputs/<document_type>/<format>/<input_file_name>_output.json
```

Running the same input file again replaces the same output file.

## Batch Evaluation

The project includes terminal commands for batch evaluation of generated images and PDFs. Each batch compares extracted fields with matching ground truth and saves per-document JSON plus an Excel accuracy and processing-time report.

The dataset is organized by document type and file format:

```text
dataset/
├── generated_docs/
│   └── <document_type>/
│       ├── image/
│       ├── pdf/
│       │   ├── scanned/
│       │   └── digital/
│       └── docx/
└── ground_truth/
    └── <document_type>/
        ├── image/
        ├── pdf/
        │   ├── scanned/
        │   └── digital/
        └── docx/
```

```bash
uv --cache-dir .uv-cache run python main.py --aadhaar-batch
uv --cache-dir .uv-cache run python main.py --pan-batch
uv --cache-dir .uv-cache run python main.py --passbook-batch
uv --cache-dir .uv-cache run python main.py --invoice-batch
```

PDF batches process every page using the ground-truth `pages` mapping:

```bash
uv --cache-dir .uv-cache run python main.py --aadhaar-pdf-batch
uv --cache-dir .uv-cache run python main.py --pan-pdf-batch
uv --cache-dir .uv-cache run python main.py --passbook-pdf-batch
uv --cache-dir .uv-cache run python main.py --invoice-pdf-batch
```

Scanned PDF batches compare the five OCR engines. Digital PDF batches compare
`pdfplumber`, `pypdf`, `pymupdf`, and `pdfminer` without converting pages to
images:

```bash
uv --cache-dir .uv-cache run python main.py --aadhaar-digital-pdf-batch
uv --cache-dir .uv-cache run python main.py --pan-digital-pdf-batch
uv --cache-dir .uv-cache run python main.py --passbook-digital-pdf-batch
```

Batch outputs are saved under:

```text
outputs/<document_type>/image/
outputs/<document_type>/pdf/
```

Each output folder contains matching JSON files and an Excel report. Reports contain `accuracy`, `quality_front`, `quality_back`, and `summary` sheets with model accuracy and processing times.

```text
outputs/aadhaar/image/aadhaar_model_accuracy.xlsx
outputs/pan/image/pan_model_accuracy.xlsx
outputs/passbook/image/passbook_model_accuracy.xlsx
outputs/invoice/image/invoice_model_accuracy.xlsx
outputs/aadhaar/pdf/aadhaar_pdf_model_accuracy.xlsx
outputs/pan/pdf/pan_pdf_model_accuracy.xlsx
outputs/passbook/pdf/passbook_pdf_model_accuracy.xlsx
outputs/invoice/pdf/invoice_pdf_model_accuracy.xlsx
outputs/aadhaar/pdf/digital/aadhaar_digital_pdf_extractor_accuracy.xlsx
outputs/pan/pdf/digital/pan_digital_pdf_extractor_accuracy.xlsx
outputs/passbook/pdf/digital/passbook_digital_pdf_extractor_accuracy.xlsx
```

The output layout is ready for all supported formats:

```text
outputs/
└── <document_type>/
    ├── image/
    ├── pdf/
    └── docx/
```

## Clear Outputs

Delete generated JSON and Excel files while keeping the output folder structure:

```bash
uv --cache-dir .uv-cache run python main.py --clear-output
```

Clear old results and immediately rebuild a batch:

```bash
uv --cache-dir .uv-cache run python main.py --clear-output --aadhaar-batch
uv --cache-dir .uv-cache run python main.py --clear-output --pan-batch
uv --cache-dir .uv-cache run python main.py --clear-output --passbook-batch
uv --cache-dir .uv-cache run python main.py --clear-output --invoice-batch
```

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

The Aadhaar schemas extract front-side fields such as Aadhaar number, VID, name, Hindi name, date or year of birth, and gender, plus back-side fields such as address, pincode, relationship label, care-of/father/husband fields, and Hindi address fields.

The PAN schema extracts PAN number, English and Hindi names, father name, date of birth, signature presence, and card issue text.

The passbook schema extracts banking fields such as bank name, branch details, IFSC, MICR, account holder, account number, PAN, address, account opening date, issue date, and branch manager stamp presence.

The invoice schema extracts company, date, address, total amount, and source image.

## Extraction Logic

The parser handles common form layouts:

- label and value on the same line
- label on one line and value on the next line
- separator-only values such as `:` or `-`
- OCR-split labels, such as `Date of` followed by `Joining:`
- common email OCR issues, such as spaces or colons inside the local part
- document classification using schema label matching
- fallback field extraction for generated Aadhaar, PAN, passbook, and invoice images
- image quality categories such as clean, blurred, skewed, cropped, low light, overexposed, and low resolution

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
- `pytesseract`
- `paddleocr`
- `paddlepaddle`
- `rapidocr`
- `onnxruntime`
- `python-doctr[torch]`

If using `uv`, install dependencies with:

```bash
uv sync
```

OCR engines used by the code:

- EasyOCR is the default image OCR engine.
- Tesseract is used when installed and available through `pytesseract`.
- PaddleOCR is used when `paddleocr` and `paddlepaddle` are installed.
- RapidOCR uses ONNX Runtime as an additional CPU-oriented comparison model.
- docTR provides a PyTorch document text detection and recognition pipeline.

Note: scanned PDF OCR requires Poppler because `pdf2image` depends on it. Tesseract OCR requires the Tesseract system application to be installed separately.

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

- Add confidence scores for OCR fields
- Add a small review/edit interface
- Add Excel input extraction if needed
- Add API support later if needed
