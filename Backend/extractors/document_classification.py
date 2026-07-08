import re
from functools import lru_cache

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
    "aadhaar_number": ["Aadhaar Number:", "Aadhaar No:", "Aadhaar:", "आधार संख्या:", "आधार नंबर:"],
    "vid": ["VID:", "VID Number:", "Virtual ID:", "वीआईडी:"],
    "name": ["Name:", "नाम:"],
    "hindi_name": ["Hindi Name:", "नाम:", "हिंदी नाम:"],
    "date_of_birth": ["Date of Birth:", "DOB:", "D.O.B:", "जन्म तिथि:", "जन्म तारीख:"],
    "year_of_birth": ["Year of Birth:", "YOB:", "जन्म वर्ष:"],
    "gender": ["Gender:", "लिंग:", "Male", "Female", "पुरुष", "महिला"],
}


# Aadhaar back schema.
# Keep only address-side fields. Relationship fields are split so comparison can
# score C/O, Father/S/O, and W/O/Husband separately.
aadhaar_back_schema = {
    "aadhaar_number": ["Aadhaar Number:", "Aadhaar No:", "Aadhaar:", "आधार संख्या:", "आधार नंबर:"],
    "vid": ["VID:", "VID Number:", "Virtual ID:", "वीआईडी:"],
    "relationship_label": ["Father:", "S/O:", "C/O:", "W/O:", "Husband:", "पिता:", "पति:", "पत्नी:", "पुत्र:", "मार्फत:"],
    "care_of": ["C/O:", "Care Of:", "मार्फत:"],
    "father_name": ["Father:", "Father Name:", "S/O:", "पिता का नाम:", "पिता:", "पुत्र:"],
    "husband_name": ["Husband:", "Husband Name:", "W/O:", "पति का नाम:", "पति:", "पत्नी:"],
    "hindi_relationship_label": ["पिता:", "पति:", "पत्नी:", "पुत्र:", "मार्फत:"],
    "hindi_care_of": ["मार्फत:"],
    "hindi_father_name": ["पिता:", "पिता का नाम:", "पुत्र:"],
    "hindi_husband_name": ["पति:", "पति का नाम:", "पत्नी:"],
    "address": ["Address:", "पता:", "आवासीय पता:"],
    "hindi_address": ["पता:"],
    "hindi_address_lines": ["पता:"],
    "pincode": ["Pincode:", "PIN Code:", "PIN:", "Postal Code:"],
}


# Backward-compatible combined schema for older code paths that still import it.
aadhaar_card_schema = {
    **aadhaar_front_schema,
    **aadhaar_back_schema,
}


aadhaar_full_schema = {
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


passbook_schema = {
    "bank_name": ["Bank", "Bank Name"],
    "hindi_bank_name": ["Bank"],
    "branch_name": ["Branch"],
    "branch_code": ["Code", "Branch Code"],
    "email": ["Email"],
    "phone": ["Phone No.", "Phone"],
    "micr": ["MICR"],
    "ifsc": ["IFSC"],
    "account_holder": ["Name"],
    "relationship_label": ["S/D/H/o", "S/O", "D/O", "H/O"],
    "father_name": ["S/D/H/o", "Father Name"],
    "cif_number": ["CIF Number"],
    "account_number": ["Account No.", "Account Number"],
    "account_type": ["A/c Type", "Account Type"],
    "address": ["Address"],
    "mop": ["MOP"],
    "account_opened": ["A/c Opening Dt", "Account Opening Date"],
    "nom_reg_no": ["Nom Reg No", "Nomination Registration Number"],
    "pan_number": ["Customer's PAN", "PAN"],
    "date_of_issue": ["Date of Issue"],
    "continuation": ["CONTINUATION"],
    "branch_manager_stamp_present": ["Branch Manager", "शाखा प्रबंधक"],
}


invoice_schema = {
    "company": ["Company", "CASH SALES", "INVOICE", "TAX INVOICE", "Receipt"],
    "date": ["Date", "Daie", "Invoice Date"],
    "address": ["Address", "Jalan", "Taman", "Lot", "No."],
    "receipt_number": ["Receipt No.", "Invoice No.", "Doc No.", "Slip No."],
    "subtotal": ["Subtotal", "Sub-total", "Total Sales"],
    "tax": ["Tax", "GST", "Total Tax"],
    "discount": ["Discount", "Disc"],
    "total": ["Total Sales", "Grand Total", "Amount", "Total", "CASH"],
    "currency": ["Currency", "RM", "MYR"],
    "source_image": ["Source Image"],
}


# All document schemas are kept here.
# Later, if we add PAN card or another form, we will add it in this dictionary.
document_schemas = {
    "employee_form": employee_form_schema,
    "aadhaar_full": aadhaar_full_schema,
    "aadhaar_front": aadhaar_front_schema,
    "aadhaar_back": aadhaar_back_schema,
    "pan_card": pan_card_schema,
    "passbook": passbook_schema,
    "invoice": invoice_schema,
}


@lru_cache(maxsize=128)
def make_text_easy_to_match(text):
    # Extracted text can have extra spaces, line breaks, missing colons, or mixed case.
    # I replace common separators with spaces, then make one simple lowercase line.
    text = text.lower()
    text = re.sub(r"[:：|._-]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=256)
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


@lru_cache(maxsize=256)
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


def build_heuristic_match(document_type, confidence, all_scores):
    schema = document_schemas[document_type]

    return {
        "document_type": document_type,
        "schema": schema,
        "confidence": confidence,
        "confidence_percent": round(confidence * 100, 2),
        "confidence_level": describe_confidence_level(confidence),
        "matched_fields": [],
        "missing_fields": list(schema.keys()),
        "matched_count": 0,
        "total_fields": len(schema),
        "all_scores": all_scores,
        "score_gap": 0,
    }


def infer_document_type_from_patterns(extracted_text):
    normalized_text = make_text_easy_to_match(extracted_text)
    compact_text = re.sub(r"[^a-z0-9]", "", extracted_text.casefold())
    has_aadhaar_number = re.search(
        r"(?<!\d)\d{4}[ \t-]*\d{4}[ \t-]*\d{4}(?!\d)",
        extracted_text,
    )

    if has_aadhaar_number:
        has_address_side_marker = (
            re.search(r"\b(sio|s/o|c/o|w/o|address|pincode|uidai)\b", normalized_text)
            or re.search(r"(?<!\d)[1-9]\d{5}(?!\d)", extracted_text)
            or any(word in extracted_text for word in ["पता", "मार्फत", "पिता"])
        )
        has_front_side_marker = re.search(
            r"\b(dob|date of birth|yob|male|female)\b",
            normalized_text,
        ) or any(word in extracted_text for word in ["जन्म", "पुरुष", "महिला"])

        if has_address_side_marker and has_front_side_marker:
            return "aadhaar_full", 0.65

        if has_address_side_marker and not has_front_side_marker:
            return "aadhaar_back", 0.55

        return "aadhaar_front", 0.5

    if re.search(r"[A-Z]{5}\d{4}[A-Z]", re.sub(r"[^A-Za-z0-9]", "", extracted_text).upper()):
        return "pan_card", 0.55

    if any(marker in normalized_text for marker in ["ifsc", "account number", "passbook", "cif number"]):
        return "passbook", 0.5

    if any(marker in normalized_text for marker in ["invoice", "cash sales", "receipt", "doc no", "total sales"]):
        return "invoice", 0.5

    if "employeeid" in compact_text or "employeename" in compact_text:
        return "employee_form", 0.5

    return None, 0


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
        heuristic_type, heuristic_confidence = infer_document_type_from_patterns(extracted_text)

        if heuristic_type:
            return build_heuristic_match(heuristic_type, heuristic_confidence, all_scores)

        selected_type = "unknown"
        selected_schema = None
    else:
        selected_type = best_match["document_type"]
        selected_schema = best_match["schema"]

    heuristic_type, heuristic_confidence = infer_document_type_from_patterns(extracted_text)

    if heuristic_type == "aadhaar_full" and selected_type in {"aadhaar_front", "aadhaar_back", "aadhaar_full"}:
        selected_type = "aadhaar_full"
        selected_schema = document_schemas[selected_type]
        best_match = {
            **best_match,
            "document_type": selected_type,
            "schema": selected_schema,
            "confidence": max(best_match["confidence"], heuristic_confidence),
            "confidence_percent": round(max(best_match["confidence"], heuristic_confidence) * 100, 2),
            "confidence_level": describe_confidence_level(max(best_match["confidence"], heuristic_confidence)),
            "total_fields": len(selected_schema),
        }

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
