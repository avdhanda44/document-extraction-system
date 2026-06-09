# --------------------------------------------------------------------------------
# # Field Extraction
# 
# This notebook cleans the raw text and pulls out the employee form fields into a JSON-ready dictionary.
# --------------------------------------------------------------------------------

import re

# Clean and match text
# These helpers make the parser more forgiving when OCR adds extra symbols, spaces, or small formatting mistakes.
def is_junk_value(value):
    value = value.strip()

    if value == "":
        return True

    return re.fullmatch(r"[:;|_\-=. ]+", value) is not None


def match_label(line, label):
    clean_label = label.rstrip(":").strip()
    pattern = rf"^\s*{re.escape(clean_label)}\s*[:：-]?\s*(.*)$"
    match = re.match(pattern, line, flags=re.IGNORECASE)

    if match is None:
        return None

    return match.group(1).strip()


def clean_email(email):
    email = email.strip()

    if "@" not in email:
        return email

    local_part, domain_part = email.split("@", 1)
    local_part = re.sub(r"[\s:;]+", ".", local_part).strip(".")
    domain_part = re.sub(r"\s+", "", domain_part).strip(".")

    return f"{local_part}@{domain_part}"

# Extract structured fields
# This handles the common ways a form can appear:
# - the label and value are on the same line
# - the label is on one line and the value is on the next line
# - OCR splits a label across two lines, such as "Date of" and "Joining:"
def extract_fields(final_text, form_schema):
    lines = [line.strip() for line in final_text.split("\n") if line.strip()]
    extracted_json = {}

    def line_is_label(line):
        for form_label in form_schema.values():
            value_part = match_label(line, form_label)

            if value_part is not None and is_junk_value(value_part):
                return True

        return False

    def find_label_value(index, form_label):
        value = match_label(lines[index], form_label)

        if value is not None:
            return value, index + 1

        if index + 1 < len(lines):
            combined_line = f"{lines[index]} {lines[index + 1]}"
            value = match_label(combined_line, form_label)

            if value is not None:
                return value, index + 2

        return None, index + 1

    for index in range(len(lines)):
        for json_key, form_label in form_schema.items():
            value, next_index = find_label_value(index, form_label)

            if value is None:
                continue

            if not is_junk_value(value):
                extracted_json[json_key] = value
                continue

            for next_line in lines[next_index:]:
                if is_junk_value(next_line):
                    continue

                if line_is_label(next_line):
                    break

                extracted_json[json_key] = next_line
                break

    for json_key in form_schema:
        extracted_json.setdefault(json_key, "")

    extracted_json["email"] = clean_email(extracted_json["email"])

    return extracted_json

