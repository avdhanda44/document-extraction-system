# Document Extraction POC

This project is a local proof of concept for extracting structured data from uploaded employee, identity, banking, and invoice documents.

The production website uses `Backend/api.py`, `Backend/pipeline.py`, and the shared processors/extractor modules. Batch model comparison and Excel reports live separately under `testing/`.

## Current Status

Implemented:

- File name validation against the local `uploads/` folder
- File type detection using file content, not only file extension
- Digital PDF text extraction with `pypdf`, `pymupdf`, `pdfminer`, and `pdfplumber`
- Scanned PDF OCR using `pdf2image` and OCR engines
- PNG/JPG image OCR using available OCR engines
- DOCX text extraction using `python-docx`
- Schema-based extraction for employee enrollment forms
- Schema-based extraction for Aadhaar, PAN, passbook, and invoice documents
- Cleanup for common OCR email mistakes
- FastAPI extraction API
- React review UI
- Human review/edit screen for extracted fields
- Reviewed JSON output saved from the website
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
- Database storage

## Project Structure

```text
document-extraction-system/
├── Backend/
│   ├── api.py
│   ├── output.py
│   ├── pipeline.py
│   ├── model_policy.py
│   ├── processors/
│   │   ├── text_extractor.py
│   │   ├── pdf_processor.py
│   │   ├── image_processor.py
│   │   ├── docx_processor.py
│   ├── extractors/
│   │   ├── document_classification.py
│   │   ├── field_mapper.py
│   │   ├── validation.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── main.jsx
│       └── styles.css
├── uploads/
├── outputs/
├── testing/
│   ├── testing.py
│   ├── reporting.py
│   ├── test-CLI/
│   ├── test-data/
│   └── test-outputs/
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

Scanned PDFs are converted to images with `pdf2image`, then read with the OCR processor. The website uses the production model policy in `Backend/model_policy.py`.

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

Run the production API from the project root:

```bash
uv --cache-dir .uv-cache run uvicorn main:app --reload
```

The website upload flow accepts a user file through the frontend, stores it temporarily in `uploads/`, extracts and validates fields, deletes the uploaded original, and saves reviewed JSON only when the user clicks save.

## React Review UI

The UI is a browser-based review workbench for the extraction pipeline. Extraction previews data on screen first; it does not save a JSON file until the user clicks **Save reviewed**.

```text
Upload document -> Extract fields -> Review/edit values -> Save reviewed JSON
```

Uploaded files are stored temporarily in:

```text
uploads/<safe_uploaded_file_name>
```

After extraction, the uploaded original is deleted. The user-reviewed JSON is stored only when the user clicks **Save reviewed**:

```text
outputs/<file_stem>_reviewed.json
```

Run the API server:

```bash
uv --cache-dir .uv-cache run uvicorn Backend.api:app --reload --host 127.0.0.1 --port 8000
```

Run the React app in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

The React app proxies `/api/*` requests to the FastAPI server at `http://127.0.0.1:8000`.

## Batch Evaluation

The project includes terminal commands for batch evaluation of generated images and PDFs. Each batch compares extracted fields with matching ground truth and saves per-document JSON plus an Excel accuracy and processing-time report.

The test data is organized by document type and file format:

```text
testing/test-data/
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
uv --cache-dir .uv-cache run python testing/testing.py --aadhaar-batch
uv --cache-dir .uv-cache run python testing/testing.py --pan-batch
uv --cache-dir .uv-cache run python testing/testing.py --passbook-batch
uv --cache-dir .uv-cache run python testing/testing.py --invoice-batch
```

PDF batches process every page using the ground-truth `pages` mapping:

```bash
uv --cache-dir .uv-cache run python testing/testing.py --aadhaar-pdf-batch
uv --cache-dir .uv-cache run python testing/testing.py --pan-pdf-batch
uv --cache-dir .uv-cache run python testing/testing.py --passbook-pdf-batch
uv --cache-dir .uv-cache run python testing/testing.py --invoice-pdf-batch
```

Scanned PDF batches compare the five OCR engines. Digital PDF batches compare
`pypdf`, `pymupdf`, `pdfminer`, and `pdfplumber` without converting pages to
images:

```bash
uv --cache-dir .uv-cache run python testing/testing.py --aadhaar-digital-pdf-batch
uv --cache-dir .uv-cache run python testing/testing.py --pan-digital-pdf-batch
uv --cache-dir .uv-cache run python testing/testing.py --passbook-digital-pdf-batch
```

Run the test suite from the project root:

```bash
uv --cache-dir .uv-cache run python -m unittest discover -s testing/test-CLI
```

Batch testing outputs are saved under:

```text
testing/test-outputs/<document_type>/image/
testing/test-outputs/<document_type>/pdf/scanned/
testing/test-outputs/<document_type>/pdf/digital/
```

Each outputs folder contains matching JSON files and an Excel report. Reports contain `accuracy`, `quality_front`, `quality_back`, and `summary` sheets with model accuracy and processing times.

```text
testing/test-outputs/aadhaar/image/aadhaar_model_accuracy.xlsx
testing/test-outputs/pan/image/pan_model_accuracy.xlsx
testing/test-outputs/passbook/image/passbook_model_accuracy.xlsx
testing/test-outputs/invoice/image/invoice_model_accuracy.xlsx
testing/test-outputs/aadhaar/pdf/scanned/aadhaar_pdf_model_accuracy.xlsx
testing/test-outputs/pan/pdf/scanned/pan_pdf_model_accuracy.xlsx
testing/test-outputs/passbook/pdf/scanned/passbook_pdf_model_accuracy.xlsx
testing/test-outputs/invoice/pdf/scanned/invoice_pdf_model_accuracy.xlsx
testing/test-outputs/aadhaar/pdf/digital/aadhaar_digital_pdf_extractor_accuracy.xlsx
testing/test-outputs/pan/pdf/digital/pan_digital_pdf_extractor_accuracy.xlsx
testing/test-outputs/passbook/pdf/digital/passbook_digital_pdf_extractor_accuracy.xlsx
```

The output layout is ready for all supported formats:

```text
testing/test-outputs/
└── <document_type>/
    ├── image/
    ├── pdf/
    │   ├── scanned/
    │   └── digital/
    └── docx/
```

## Clear Outputs

Delete generated JSON and Excel files while keeping the outputs folder structure:

```bash
uv --cache-dir .uv-cache run python testing/testing.py --clear-output
```

Clear old results and immediately rebuild a batch:

```bash
uv --cache-dir .uv-cache run python testing/testing.py --clear-output --aadhaar-batch
uv --cache-dir .uv-cache run python testing/testing.py --clear-output --pan-batch
uv --cache-dir .uv-cache run python testing/testing.py --clear-output --passbook-batch
uv --cache-dir .uv-cache run python testing/testing.py --clear-output --invoice-batch
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

The invoice schema extracts company, date, address, receipt number, subtotal,
tax, discount, total, currency, and source image. The current invoice ground
truth evaluates company, date, address, and total; source-image metadata is not
counted as model accuracy.

Invoice batch reports contain:

- `accuracy`: per-image model accuracy and processing time
- `field_accuracy`: average accuracy and similarity for each evaluated field
- `summary`: average accuracy, speed, failures, and complete-record rate by model

Scanned PDF JSON and Excel reports are saved under
`testing/test-outputs/<document_type>/pdf/scanned/`. Digital PDF reports are saved under
`testing/test-outputs/<document_type>/pdf/digital/`.

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
- `fastapi`
- `pdfplumber`
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
- `reportlab`
- `pypdf`
- `pymupdf`
- `python-multipart`
- `uvicorn[standard]`

If using `uv`, install dependencies with:

```bash
uv sync
```

OCR engines used by the code:

- The website uses the production model policy in `Backend/model_policy.py`.
- Digital PDFs try `pypdf`, `pymupdf`, `pdfminer`, then `pdfplumber`.
- Images and scanned PDFs try available OCR engines in policy order, currently `doctr`, `paddleocr`, then `easyocr`.
- Tesseract is used when installed and available through `pytesseract`.
- PaddleOCR is used when `paddleocr` and `paddlepaddle` are installed.
- Invoice batches run PaddleOCR in English-only mode for this English receipt dataset.
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
- Run `testing/testing.py` from the project root for batch evaluation.
- Do not manually edit generated JSON files unless testing output formatting.
- If field extraction is wrong, first inspect the raw extracted text from the processor output during debugging.
- If OCR reads a value incorrectly, inspect the image quality and OCR output.
- If a new file type is needed, update `detect_uploaded_file_type()` and `extract_text_by_file_type()` in `Backend/processors/text_extractor.py`.

## Roadmap

Planned next steps:

- Add confidence scores for OCR fields
- Add Excel input extraction if needed
- Add database storage if needed
