# --------------------------------------------------------------------------------
# # Project Setup
# 
# This notebook prepares the shared pieces used by the POC: imports, folder paths, field names, and a small file-name safety check.
# --------------------------------------------------------------------------------

# Imports
# These libraries are used across the helper notebooks and the main POC run.
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import easyocr
import pdfplumber
import ipywidgets as widgets
from docx import Document
from IPython.display import display
from pdf2image import convert_from_path

# Project folders
# Input documents should be placed in uploads. Extracted JSON files will be saved in outputs.
cwd = Path.cwd()
project_root = cwd
if not (cwd / "uploads").exists() and not (cwd / "outputs").exists():
    parent = cwd.parent
    if (parent / "uploads").exists() or (parent / "outputs").exists():
        project_root = parent
uploads_folder = project_root / "uploads"
outputs_folder = project_root / "outputs"

uploads_folder.mkdir(exist_ok=True)
outputs_folder.mkdir(exist_ok=True)

print("Upload folder:", uploads_folder.resolve())
print("Output folder:", outputs_folder.resolve())

# Form fields
# The left side is the JSON key we want in the output.
# The right side is the label text we expect to find in the form.
form_schema = {
    "employee_name": "Employee Name:",
    "employee_id": "Employee ID:",
    "date_of_birth": "Date of Birth:",
    "date_of_joining": "Date of Joining:",
    "department": "Department:",
    "designation": "Designation:",
    "mobile_number": "Mobile Number:",
    "email": "Email:",
    "address": "Address:",
    "pincode": "Pincode:"
}

# Validate the typed file name
# This keeps the user inside the uploads folder and gives a clear error if the file is missing.
def get_file_path(file_name):
    file_name = file_name.strip()

    if file_name == "":
        raise ValueError("Error: give valid file name")

    file_path = uploads_folder / file_name

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("Error: give valid file name")

    return file_path

