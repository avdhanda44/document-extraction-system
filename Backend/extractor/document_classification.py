import re
import regex as fuzzy_regex


# Employee form schema.
# The key is our clean field name, and the value is the label written in the document.
employee_form_schema = {
    "employee_name": "Employee Name:",
    "employee_id": "Employee ID:",
    "date_of_birth": "Date of Birth:",
    "date_of_joining": "Date of Joining:",
    "department": "Department:",
    "designation": "Designation:",
    "mobile_number": "Mobile Number:",
    "email": "Email:",
    "address": "Address:",
    "pincode": "Pincode:",
}


# Aadhaar front schema.
# Keep only the fields that can appear on the front side of an Aadhaar card.
aadhaar_front_schema = {
    "aadhaar_number": ["Aadhaar Number:", "आधार संख्या:", "आधार नंबर:"],
    "vid": ["VID:", "वीआईडी:"],
    "name": ["Name:", "नाम:"],
    "hindi_name": ["Hindi Name:", "नाम:"],
    "date_of_birth": ["Date of Birth:", "DOB:", "जन्म तिथि:"],
    "year_of_birth": ["Year of Birth:", "YOB:", "जन्म वर्ष:"],
    "gender": ["Gender:", "लिंग:", "Male", "Female", "पुरुष", "महिला"],
}


# Aadhaar back schema.
# Keep only address-side fields. Relationship fields are split so comparison can
# score C/O, Father/S/O, and W/O/Husband separately.
aadhaar_back_schema = {
    "aadhaar_number": ["Aadhaar Number:", "आधार संख्या:", "आधार नंबर:"],
    "vid": ["VID:", "वीआईडी:"],
    "relationship_label": ["Father:", "S/O:", "C/O:", "W/O:", "Husband:", "पिता:", "पति:", "मार्फत:"],
    "care_of": ["C/O:", "Care Of:", "मार्फत:"],
    "father_name": ["Father:", "Father Name:", "S/O:", "पिता का नाम:", "पिता:"],
    "husband_name": ["Husband:", "Husband Name:", "W/O:", "पति का नाम:", "पति:"],
    "hindi_relationship_label": ["पिता:", "पति:", "पत्नी:", "पुत्र:", "मार्फत:"],
    "hindi_care_of": ["मार्फत:"],
    "hindi_father_name": ["पिता:", "पिता का नाम:", "पुत्र:"],
    "hindi_husband_name": ["पति:", "पति का नाम:", "पत्नी:"],
    "address": ["Address:", "पता:"],
    "hindi_address": ["पता:"],
    "hindi_address_lines": ["पता:"],
    "pincode": ["Pincode:", "PIN Code:", "Postal Code:"],
}


# Backward-compatible combined schema for older code paths that still import it.
aadhaar_card_schema = {
    **aadhaar_front_schema,
    **aadhaar_back_schema,
}


pan_card_schema = {
    "pan_number": ["Permanent Account Number", "PAN", "PAN Number"],
    "name": ["Name", "नाम"],
    "hindi_name": ["नाम"],
    "father_name": ["Father's Name", "Father Name", "पिता का नाम"],
    "hindi_father_name": ["पिता का नाम"],
    "date_of_birth": ["Date of Birth", "जन्म की तारीख"],
    "signature_present": ["Signature", "हस्ताक्षर"],
    "card_issue_date_text": ["Issue Date", "Card Issue Date"],
}


# All document schemas are kept here.
# Later, if we add PAN card or another form, we will add it in this dictionary.
document_schemas = {
    "employee_form": employee_form_schema,
    "aadhaar_front": aadhaar_front_schema,
    "aadhaar_back": aadhaar_back_schema,
    "pan_card": pan_card_schema,
}


def make_text_easy_to_match(text):
    # Extracted text can have extra spaces, line breaks, missing colons, or mixed case.
    # I replace common separators with spaces, then make one simple lowercase line.
    text = text.lower()
    text = re.sub(r"[:：|._-]+", " ", text)
    return " ".join(text.split())


def make_label_easy_to_match(label):
    # Make schema labels match the same style as extracted text.
    # Example: "Employee Name:" and "employee-name" both become "employee name".
    label = label.lower()
    label = re.sub(r"[:：|._-]+", " ", label)
    return " ".join(label.split())


def get_labels_for_field(label_or_labels):
    # A field can have one label or many labels.
    # This makes both cases work the same way.
    if isinstance(label_or_labels, list):
        return label_or_labels

    return [label_or_labels]


def get_allowed_fuzzy_errors(label):
    # Fuzzy matching means we allow a few small OCR mistakes in labels.
    # Short labels like DOB or VID should stay strict, otherwise they may match wrong text.
    label_length = len(label.replace(" ", ""))

    if label_length <= 4:
        return 0

    if label_length <= 12:
        return 1

    return 2


def text_has_label_with_fuzzy_match(normalized_text, normalized_label):
    # First try normal matching because it is easiest and fastest.
    if normalized_label in normalized_text:
        return True

    allowed_errors = get_allowed_fuzzy_errors(normalized_label)

    if allowed_errors == 0:
        return False

    # regex fuzzy matching allows small insert/delete/substitute mistakes.
    # Example: "moblle number" can still match "mobile number".
    fuzzy_pattern = f"({fuzzy_regex.escape(normalized_label)}){{e<={allowed_errors}}}"

    return fuzzy_regex.search(fuzzy_pattern, normalized_text) is not None


def compare_text_with_one_schema(extracted_text, schema):
    # Check one schema against the extracted text.
    # We save matched and missing fields so we can explain why a document type was selected.
    normalized_text = make_text_easy_to_match(extracted_text)
    matched_fields = []
    missing_fields = []

    for field_name, label_or_labels in schema.items():
        # Get all possible labels for this field.
        possible_labels = get_labels_for_field(label_or_labels)
        normalized_labels = [make_label_easy_to_match(label) for label in possible_labels]

        if any(text_has_label_with_fuzzy_match(normalized_text, label) for label in normalized_labels):
            matched_fields.append(field_name)
        else:
            missing_fields.append(field_name)

    total_fields = len(schema)
    # Confidence = matched fields / total fields.
    # Example: 8 out of 10 fields matched = 80%.
    confidence = len(matched_fields) / total_fields if total_fields else 0

    return {
        "matched_fields": matched_fields,
        "missing_fields": missing_fields,
        "matched_count": len(matched_fields),
        "total_fields": total_fields,
        "confidence": confidence,
    }


def describe_confidence_level(confidence):
    # These words make the confidence score easier to read.
    # We can tune these limits later after testing more files.
    if confidence >= 0.8:
        return "high"

    if confidence >= 0.5:
        return "medium"

    return "low"


def choose_document_type_from_text(extracted_text):
    # Check the text against every schema we know.
    # The schema with the highest confidence becomes the selected document type.
    all_scores = []

    for document_type, schema in document_schemas.items():
        # Check one document type and save its score.
        match_details = compare_text_with_one_schema(extracted_text, schema)

        all_scores.append({
            "document_type": document_type,
            "schema": schema,
            "confidence": match_details["confidence"],
            "confidence_percent": round(match_details["confidence"] * 100, 2),
            "confidence_level": describe_confidence_level(match_details["confidence"]),
            "matched_fields": match_details["matched_fields"],
            "missing_fields": match_details["missing_fields"],
            "matched_count": match_details["matched_count"],
            "total_fields": match_details["total_fields"],
        })

    # Put the best score first.
    all_scores = sorted(all_scores, key=lambda item: item["confidence"], reverse=True)

    if not all_scores:
        return {
            "document_type": "unknown",
            "schema": None,
            "confidence": 0,
            "confidence_percent": 0,
            "confidence_level": "low",
            "matched_fields": [],
            "missing_fields": [],
            "matched_count": 0,
            "total_fields": 0,
            "all_scores": [],
            "score_gap": 0,
        }

    best_match = all_scores[0]
    # Score gap shows how far the best schema is from the second best.
    # Bigger gap means the decision is clearer.
    second_best_confidence = all_scores[1]["confidence"] if len(all_scores) > 1 else 0
    score_gap = best_match["confidence"] - second_best_confidence

    # If confidence is too low, keep document type as unknown.
    # For now, at least 40% of labels should match.
    if best_match["confidence"] < 0.4:
        selected_type = "unknown"
        selected_schema = None
    else:
        selected_type = best_match["document_type"]
        selected_schema = best_match["schema"]

    return {
        "document_type": selected_type,
        "schema": selected_schema,
        "confidence": best_match["confidence"],
        "confidence_percent": best_match["confidence_percent"],
        "confidence_level": best_match["confidence_level"],
        "matched_fields": best_match["matched_fields"],
        "missing_fields": best_match["missing_fields"],
        "matched_count": best_match["matched_count"],
        "total_fields": best_match["total_fields"],
        "all_scores": all_scores,
        "score_gap": round(score_gap * 100, 2),
    }
