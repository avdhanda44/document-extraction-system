# --------------------------------------------------------------------------------
# # Validation
# 
# This notebook provides reusable validation functions for post-extraction checks. It contains no demo or execution cells — only pure validation helpers.
# --------------------------------------------------------------------------------

import re
from datetime import datetime

required_fields = [
    "employee_name",
    "employee_id",
    "date_of_birth",
    "date_of_joining",
    "mobile_number",
    "email"
]

optional_fields = [
    "department",
    "designation",
    "address",
    "pincode"
]

# Validators

def validate_email(email):
    """Return (valid: bool, error: str, warning: str)"""
    email = (email or "").strip()
    if email == "":
        return False, "Required field missing", ""

    # Basic email regex: local@domain.tld
    pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    if re.match(pattern, email):
        return True, "", ""

    return False, "Invalid email format", ""


def validate_mobile_number(number):
    """Normalize number and check it has exactly 10 digits."""
    number = (number or "").strip()
    if number == "":
        return False, "Required field missing", ""

    # remove spaces, hyphens, parentheses
    norm = re.sub(r"[\s\-()]+", "", number)
    if not norm.isdigit():
        return False, "Mobile number must contain only digits", ""

    if len(norm) == 10:
        return True, "", ""

    return False, "Mobile number must have exactly 10 digits", ""


def validate_pincode(pincode):
    pincode = (pincode or "").strip()
    if pincode == "":
        return False, "Required field missing", ""

    norm = re.sub(r"\s+", "", pincode)
    if norm.isdigit() and len(norm) == 6:
        return True, "", ""

    return False, "Pincode must be exactly 6 digits", ""


def validate_date(date_string):
    s = (date_string or "").strip()
    if s == "":
        return False, "Required field missing", ""

    # Supported formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
    patterns = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in patterns:
        try:
            dt = datetime.strptime(s, fmt)
            return True, "", ""
        except Exception:
            continue

    return False, "Invalid date format or value", ""


def validate_employee_id(employee_id):
    eid = (employee_id or "").strip()
    if eid == "":
        return False, "Required field missing", ""

    if re.match(r'^[A-Za-z0-9_-]+$', eid):
        return True, "", ""

    return False, "Employee ID must contain only letters, numbers, hyphens or underscores", ""


def validate_required_field(value, field_label):
    v = (value or "").strip()
    if v == "":
        return False, "Required field missing"
    return True, ""


# Main orchestration

def validate_extracted_fields(extracted_json):
    """Validate extracted fields and return the required output structure.

    Returns:
        {
            "extracted_data": {...},
            "validation_results": { field: {value, valid, error, warning}},
            "validation_summary": { ... }
        }
    """
    # Ensure keys exist and missing values are empty strings
    extracted_data = {k: (extracted_json.get(k, '') if isinstance(extracted_json, dict) else '') for k in (required_fields + optional_fields)}

    validation_results = {}
    invalid_fields = 0
    warnings = 0
    total_checked = 0

    for field in required_fields + optional_fields:
        total_checked += 1
        value = extracted_data.get(field, '')
        result = {"value": value, "valid": True, "error": "", "warning": ""}

        # Required/optional handling
        if field in required_fields:
            if (value or "").strip() == "":
                result["valid"] = False
                result["error"] = "Required field missing"
                invalid_fields += 1
                validation_results[field] = result
                continue
        else:
            if (value or "").strip() == "":
                # optional missing => valid but warning
                result["valid"] = True
                result["warning"] = "Optional field missing"
                warnings += 1
                validation_results[field] = result
                continue

        # Field-specific validations
        if field == "email":
            valid, err, warn = validate_email(value)
            result["valid"] = valid
            result["error"] = err
            result["warning"] = warn
            if not valid:
                invalid_fields += 1

        elif field == "mobile_number":
            valid, err, warn = validate_mobile_number(value)
            result["valid"] = valid
            result["error"] = err
            result["warning"] = warn
            if not valid:
                invalid_fields += 1

        elif field == "pincode":
            valid, err, warn = validate_pincode(value)
            result["valid"] = valid
            result["error"] = err
            result["warning"] = warn
            if not valid:
                invalid_fields += 1

        elif field in ("date_of_birth", "date_of_joining"):
            valid, err, warn = validate_date(value)
            result["valid"] = valid
            result["error"] = err
            result["warning"] = warn
            if not valid:
                invalid_fields += 1

        elif field == "employee_id":
            valid, err, warn = validate_employee_id(value)
            result["valid"] = valid
            result["error"] = err
            result["warning"] = warn
            if not valid:
                invalid_fields += 1

        # For other fields no extra format validation
        validation_results[field] = result

    summary = {
        "total_fields_checked": total_checked,
        "valid_fields": total_checked - invalid_fields,
        "invalid_fields": invalid_fields,
        "fields_with_warnings": warnings,
        "ready_to_save": (invalid_fields == 0),
        "requires_review": (invalid_fields > 0)
    }

    return {
        "extracted_data": extracted_data,
        "validation_results": validation_results,
        "validation_summary": summary
    }

