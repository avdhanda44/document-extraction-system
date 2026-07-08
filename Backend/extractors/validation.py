import re
from datetime import datetime


# These rules tell validation which fields are required and which are optional.
# If we add a new schema later but forget to add rules here,
# the code will still work by treating all fields from that schema as required.
document_validation_rules = {
    "employee_form": {
        "required": [
            "employee_name",
            "employee_id",
            "date_of_birth",
            "date_of_joining",
            "mobile_number",
            "email",
        ],
        "optional": [
            "department",
            "designation",
            "address",
            "pincode",
        ],
    },
    "aadhaar_card": {
        "required": [
            "aadhaar_number",
            "name",
            "gender",
        ],
        "optional": [
            "date_of_birth",
            "year_of_birth",
            "address",
            "father_name",
            "husband_name",
            "mobile_number",
            "vid",
        ],
    },
    "aadhaar_full": {
        "required": [
            "aadhaar_number",
            "name",
            "gender",
            "address",
            "pincode",
        ],
        "optional": [
            "vid",
            "hindi_name",
            "date_of_birth",
            "year_of_birth",
            "relationship_label",
            "care_of",
            "father_name",
            "husband_name",
            "hindi_relationship_label",
            "hindi_care_of",
            "hindi_father_name",
            "hindi_husband_name",
            "hindi_address",
            "hindi_address_lines",
        ],
    },
    "aadhaar_front": {
        "required": [
            "aadhaar_number",
            "name",
            "gender",
        ],
        "optional": [
            "vid",
            "hindi_name",
            "date_of_birth",
            "year_of_birth",
        ],
    },
    "aadhaar_back": {
        "required": [
            "aadhaar_number",
            "address",
            "pincode",
        ],
        "optional": [
            "vid",
            "relationship_label",
            "care_of",
            "father_name",
            "husband_name",
            "hindi_relationship_label",
            "hindi_care_of",
            "hindi_father_name",
            "hindi_husband_name",
            "hindi_address",
            "hindi_address_lines",
        ],
    },
    "pan_card": {
        "required": [
            "pan_number",
            "name",
            "father_name",
            "date_of_birth",
        ],
        "optional": [
            "hindi_name",
            "hindi_father_name",
            "signature_present",
            "card_issue_date_text",
        ],
    },
    "passbook": {
        "required": [
            "bank_name",
            "branch_name",
            "ifsc",
            "account_holder",
            "father_name",
            "cif_number",
            "account_number",
            "account_type",
            "address",
            "account_opened",
            "pan_number",
            "date_of_issue",
        ],
        "optional": [
            "hindi_bank_name",
            "branch_code",
            "email",
            "phone",
            "micr",
            "relationship_label",
            "mop",
            "nom_reg_no",
            "continuation",
            "branch_manager_stamp_present",
        ],
    },
    "invoice": {
        "required": [
            "company",
            "date",
            "address",
            "total",
        ],
        "optional": [
            "receipt_number",
            "subtotal",
            "tax",
            "discount",
            "currency",
            "source_image",
        ],
    },
}


def check_email(email):
    email = (email or "").strip().lower()

    if email == "":
        return False, "Required field missing", ""

    # Sometimes OCR adds spaces around @ or dots, so remove spaces first.
    email = re.sub(r"\s+", "", email)

    # Simple email rule: something@something.something
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    if re.match(pattern, email):
        return True, "", ""

    return False, "Invalid email format", ""


def check_mobile_number(number):
    number = (number or "").strip()

    if number == "":
        return False, "Required field missing", ""

    # Remove common separators before checking the number.
    digits_only = re.sub(r"[\s\-().]+", "", number)

    if not digits_only.isdigit():
        return False, "Mobile number must contain only digits", ""

    if len(digits_only) == 10:
        return True, "", ""

    return False, "Mobile number must have exactly 10 digits", ""


def check_pincode(pincode):
    pincode = (pincode or "").strip()

    if pincode == "":
        return True, "", "Optional field missing"

    # Pincode may come with spaces or hyphens from OCR, so remove them first.
    digits_only = re.sub(r"[\s\-]+", "", pincode)

    if digits_only.isdigit() and len(digits_only) == 6:
        return True, "", ""

    return False, "Pincode must be exactly 6 digits", ""


def check_date(date_text):
    date_text = (date_text or "").strip()

    if date_text == "":
        return False, "Required field missing", ""

    # These are the date formats we accept right now.
    # Spaces around separators are removed before checking.
    date_text = re.sub(r"\s*([/.-])\s*", r"\1", date_text)
    accepted_formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"]

    for date_format in accepted_formats:
        try:
            datetime.strptime(date_text, date_format)
            return True, "", ""
        except Exception:
            pass

    return False, "Invalid date format or value", ""


def check_employee_id(employee_id):
    employee_id = (employee_id or "").strip()

    if employee_id == "":
        return False, "Required field missing", ""

    # Employee ID can contain letters, numbers, hyphen, and underscore.
    if re.match(r"^[A-Za-z0-9_-]+$", employee_id):
        return True, "", ""

    return False, "Employee ID must contain only letters, numbers, hyphens or underscores", ""


def check_aadhaar_number(aadhaar_number):
    aadhaar_number = (aadhaar_number or "").strip()

    if aadhaar_number == "":
        return False, "Required field missing", ""

    # Aadhaar is often printed with spaces or hyphens, like 1234 5678 9012.
    digits_only = re.sub(r"[\s\-]+", "", aadhaar_number)

    if digits_only.isdigit() and len(digits_only) == 12:
        return True, "", ""

    return False, "Aadhaar number must have exactly 12 digits", ""


def check_vid(vid):
    vid = (vid or "").strip()

    if vid == "":
        return True, "", "Optional field missing"

    # VID is optional, but if present it should be 16 digits.
    digits_only = re.sub(r"[\s\-]+", "", vid)

    if digits_only.isdigit() and len(digits_only) == 16:
        return True, "", ""

    return False, "VID must have exactly 16 digits", ""


def check_pan_number(pan_number):
    pan_number = (pan_number or "").strip().upper()

    if pan_number == "":
        return False, "Required field missing", ""

    pan_number = re.sub(r"[^A-Z0-9]", "", pan_number)

    if re.match(r"^[A-Z]{5}\d{4}[A-Z]$", pan_number):
        return True, "", ""

    return False, "PAN number must match format AAAAA9999A", ""


def check_ifsc(ifsc):
    ifsc = (ifsc or "").strip().upper()

    if ifsc == "":
        return False, "Required field missing", ""

    ifsc = re.sub(r"[^A-Z0-9]", "", ifsc)

    if re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc):
        return True, "", ""

    return False, "IFSC must match format AAAA0999999", ""


def check_micr(micr):
    micr = (micr or "").strip()

    if micr == "":
        return True, "", "Optional field missing"

    digits_only = re.sub(r"\D", "", micr)

    if len(digits_only) == 9:
        return True, "", ""

    return False, "MICR must have exactly 9 digits", ""


def check_account_number(account_number):
    account_number = (account_number or "").strip()

    if account_number == "":
        return False, "Required field missing", ""

    digits_only = re.sub(r"\D", "", account_number)

    if 9 <= len(digits_only) <= 18:
        return True, "", ""

    return False, "Account number must have 9 to 18 digits", ""


def check_numeric_identifier(value, field_label, required=True):
    value = (value or "").strip()

    if value == "":
        if required:
            return False, "Required field missing", ""
        return True, "", "Optional field missing"

    if re.sub(r"\D", "", value):
        return True, "", ""

    return False, f"{field_label} must contain digits", ""


def check_boolean_or_text(value):
    if isinstance(value, bool):
        return True, "", ""

    value = str(value or "").strip()

    if value == "":
        return True, "", "Optional field missing"

    if value.casefold() in {"true", "false", "yes", "no", "present", "missing"}:
        return True, "", ""

    return False, "Value must be boolean-like", ""


def check_invoice_total(total):
    total = (total or "").strip()

    if total == "":
        return False, "Required field missing", ""

    total = total.replace(",", "")
    total = re.sub(r"^[A-Za-z$]+", "", total).strip()

    if re.match(r"^\d+(?:\.\d{2})?$", total):
        return True, "", ""

    return False, "Total must be a valid amount", ""


def get_required_and_optional_fields(document_type, schema):
    # Use rules for only the document type selected by document classification.
    if document_type in document_validation_rules:
        rules = document_validation_rules[document_type]
        return rules["required"], rules["optional"]

    # Future schemas still work even before we write custom rules.
    # In that case all schema fields are treated as required.
    return list(schema.keys()), []


def check_field_format(field_name, value):
    # These format checks work across document types if the field names are the same.
    if field_name == "email":
        return check_email(value)

    if field_name == "mobile_number":
        return check_mobile_number(value)

    if field_name == "pincode":
        return check_pincode(value)

    if field_name in ["date_of_birth", "date_of_joining"]:
        return check_date(value)

    if field_name == "employee_id":
        return check_employee_id(value)

    if field_name == "aadhaar_number":
        return check_aadhaar_number(value)

    if field_name == "vid":
        return check_vid(value)

    if field_name == "pan_number":
        return check_pan_number(value)

    if field_name == "ifsc":
        return check_ifsc(value)

    if field_name == "micr":
        return check_micr(value)

    if field_name == "account_number":
        return check_account_number(value)

    if field_name == "cif_number":
        return check_numeric_identifier(value, "CIF number")

    if field_name == "nom_reg_no":
        return check_numeric_identifier(value, "Nomination registration number", required=False)

    if field_name == "branch_code":
        return check_numeric_identifier(value, "Branch code", required=False)

    if field_name in ["account_opened", "date_of_issue"]:
        return check_date(value)

    if field_name == "branch_manager_stamp_present":
        return check_boolean_or_text(value)

    if field_name == "total":
        return check_invoice_total(value)

    return True, "", ""


def validate_one_field(field_name, value, required_fields, optional_fields):
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)

    value = str(value or "").strip()

    if field_name in required_fields and value == "":
        return False, "Required field missing", ""

    if field_name in optional_fields and value == "":
        return True, "", "Optional field missing"

    return check_field_format(field_name, value)


def validate_extracted_fields(classification, mapped_fields):
    # Main validation function used by main.py.
    # We do not classify again here. We use the document type already selected earlier.
    document_type = classification["document_type"]
    schema = classification["schema"]

    if schema is None:
        return {
            "extracted_data": mapped_fields,
            "validation_results": {},
            "validation_summary": {
                "total_fields_checked": 0,
                "valid_fields": 0,
                "invalid_fields": 0,
                "fields_with_warnings": 0,
                "ready_to_save": False,
                "requires_review": True,
                "note": "Document type is unknown, so validation could not run.",
            },
        }

    required_fields, optional_fields = get_required_and_optional_fields(document_type, schema)
    expected_fields = required_fields + optional_fields
    extracted_data = {field: mapped_fields.get(field, "") for field in expected_fields}

    validation_results = {}
    invalid_count = 0
    warning_count = 0

    for field_name in expected_fields:
        value = extracted_data[field_name]
        is_valid, error, warning = validate_one_field(field_name, value, required_fields, optional_fields)

        if not is_valid:
            invalid_count += 1

        if warning:
            warning_count += 1

        validation_results[field_name] = {
            "value": value,
            "valid": is_valid,
            "error": error,
            "warning": warning,
        }

    total_fields = len(expected_fields)

    validation_summary = {
        "document_type": document_type,
        "total_fields_checked": total_fields,
        "valid_fields": total_fields - invalid_count,
        "invalid_fields": invalid_count,
        "fields_with_warnings": warning_count,
        "ready_to_save": invalid_count == 0,
        "requires_review": invalid_count > 0,
    }

    return {
        "extracted_data": extracted_data,
        "validation_results": validation_results,
        "validation_summary": validation_summary,
    }
