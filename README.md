# Intelligent Document Extraction System

## Project Overview

This project focuses on building an intelligent document extraction system capable of automatically processing multiple document formats and extracting structured information for business workflows and form automation.

The primary goal is to reduce manual data entry by converting uploaded documents into machine-readable structured JSON outputs.

The system is being designed in a modular and scalable way so that additional document types, extraction methods, and AI capabilities can be integrated in future phases.

---

# Problem Statement

Organizations often receive documents in multiple formats such as:

- Employee enrollment forms
- Identification documents
- Policy forms
- Scanned PDFs
- Images of forms

Manually extracting information from these documents is time-consuming and error-prone.

This project aims to automate that process by:

- Detecting document type
- Extracting text
- Identifying predefined fields
- Returning structured JSON output
- Supporting future multilingual and AI-based extraction workflows

---

# Current Project Status

## Completed Features

### 1. Local Document Processing Pipeline
- Local project environment setup
- Structured project folder organization
- Uploads and outputs management

---

### 2. File Validation
The system currently validates:

- Empty filename detection
- File existence
- Valid file path checking

---

### 3. Real File Type Detection
The system does not rely only on file extensions.

Actual file signatures (magic bytes) are used to detect:

- PNG
- JPG/JPEG
- PDF
- Office document signatures

Example:
- A fake `.pdf` renamed from an image can still be detected correctly.

---

### 4. OCR Extraction for Images
Implemented OCR pipeline using:

- EasyOCR

Current image support:
- PNG
- JPG/JPEG

Capabilities:
- Detect text regions
- Extract text
- Generate clean text output

---

### 5. PDF Processing
Implemented:
- Digital PDF detection
- Text extraction using `pdfplumber`

Current workflow:
- If PDF contains machine-readable text → extract directly
- If no readable text exists → classify as scanned PDF

---

### 6. Scanned PDF Detection
The system can already identify scanned PDFs.

Planned next step:
- Convert scanned PDF pages into images
- Pass pages through OCR pipeline

---

### 7. Schema-Based Field Extraction
Implemented extraction of predefined fields using form schema mapping.

Current supported fields:

- Employee Name
- Employee ID
- Date of Birth
- Date of Joining
- Department
- Designation
- Mobile Number
- Email
- Address
- Pincode

---

### 8. Structured JSON Output
The extracted information is converted into structured JSON format.

Example:

```json
{
    "employee_name": "Arjun Mehta",
    "employee_id": "EMP-9153",
    "department": "Product Management"
}
```

JSON outputs are automatically timestamped and saved inside the outputs folder.

---

# Current Architecture

```text
Document Upload
        ↓
File Validation
        ↓
Actual File Type Detection
        ↓
Image OCR OR PDF Extraction
        ↓
Clean Text Generation
        ↓
Schema-Based Field Extraction
        ↓
Structured JSON Output
```

---

# Technologies Used

## Programming Language
- Python

## OCR
- EasyOCR

## PDF Processing
- pdfplumber

## Environment
- Jupyter Notebook
- VS Code

## Data Format
- JSON

## File Handling
- pathlib

---

# Current Limitations

The current version is intentionally focused on building a stable foundational pipeline.

Not yet implemented:

- Scanned PDF OCR processing
- DOCX support
- Excel support
- Multilingual OCR
- Human review UI
- Database integration
- API deployment
- NER-based extraction
- Cloud hosting

---

# Planned Future Enhancements

## 1. Scanned PDF OCR Pipeline
PDF → Image Conversion → OCR

---

## 2. Multilingual Support
Planned language support:
- English
- Hindi
- Additional Indian regional languages

---

## 3. Named Entity Recognition (NER)
NER will later help with:
- Unstructured documents
- Flexible document layouts
- Sentence-level extraction

---

## 4. Human Review Interface
Users will be able to:
- Review extracted values
- Edit incorrect fields
- Approve final structured data

---

## 5. API & UI Development
Future plans include:
- FastAPI backend
- Streamlit interface
- Web upload system

---

## 6. Database Integration
Planned support for:
- PostgreSQL
- MongoDB
- Cloud storage systems

---

# End Goal

The long-term objective is to build a scalable intelligent document processing platform capable of:

- Handling multiple document types
- Supporting multilingual extraction
- Automating form-filling workflows
- Reducing manual processing effort
- Generating reliable structured outputs
- Integrating with enterprise business systems

The system is being designed incrementally, starting from core OCR and structured extraction foundations before moving into advanced AI-assisted workflows.

---

# Repository Structure

```text
document_extractor/
│
├── uploads/
├── outputs/
├── document_extraction_poc.ipynb
├── main.py
├── README.md
├── pyproject.toml
└── .gitignore
```

---

# Current Development Approach

The project is currently being developed and tested locally with sample documents and iterative improvements before moving toward deployment and broader collaboration/testing workflows.