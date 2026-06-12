import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from Backend.extractor.document_classification import (
    aadhaar_back_schema,
    aadhaar_front_schema,
    choose_document_type_from_text,
    describe_confidence_level,
    pan_card_schema,
)
from Backend.extractor.field_mapper import extract_field_values_using_schema
from Backend.extractor.validation import validate_extracted_fields
from Backend.json_generator import (
    create_final_json_output,
    save_aadhaar_json_file,
    save_accuracy_excel,
    save_document_json_file,
    save_final_json_file,
)
from Backend.processor.image_processor import extract_text_from_image, get_available_ocr_models
from Backend.processor.text_extractor import extract_uploaded_document


project_folder = Path(__file__).resolve().parent
aadhaar_images_folder = project_folder / "dataset" / "employee_docs" / "generated_docs" / "aadhaar"
aadhaar_ground_truth_folder = project_folder / "dataset" / "employee_docs" / "ground_truth" / "aadhaar"
pan_images_folder = project_folder / "dataset" / "employee_docs" / "generated_docs" / "pan"
pan_ground_truth_folder = project_folder / "dataset" / "employee_docs" / "ground_truth" / "pan"
image_extensions = {".png", ".jpg", ".jpeg"}
aadhaar_footer_words = [
    "www",
    "uidai",
    "help@",
    "help @",
    "1947",
    "qr",
    "government of india",
    "bharat sarkar",
    "unique identification",
    "mera aadhaar",
    "aadhaar is proof",
    "aadhar is proof",
    "sample photo",
    "bengaluru-560 001",
    "bengaluru 560 001",
]
image_quality_categories = [
    "jpeg_heavy_compression",
    "low_resolution",
    "mobile_photo",
    "partial_crop",
    "overexposed",
    "low_light",
    "blurred",
    "shadow",
    "skewed",
    "cropped",
    "rotated",
    "clean",
]


def run_document_processing(file_name):
    # This function controls the full process from file name to final JSON.

    # Get the file name and remove extra spaces.
    file_name = file_name.strip()

    # If no file name is typed, stop here and ask for one.
    if file_name == "":
        print("Please enter a file name from the uploads folder.")
        return

    try:
        # Step 1: read the uploaded document and get raw text.
        result = extract_uploaded_document(file_name)

        # Step 2: use the raw text to decide which schema fits best.
        classification = choose_document_type_from_text(result["final_text"])

        # Step 3: if we know the schema, extract values for each field.
        if classification["schema"] is not None:
            mapped_fields = extract_field_values_using_schema(result["final_text"], classification["schema"])
        else:
            mapped_fields = {}

        # Step 4: validate the mapped fields before saving.
        validation = validate_extracted_fields(classification, mapped_fields)

        # Step 5: create the final JSON and save it in outputs.
        final_json = create_final_json_output(result, classification, mapped_fields, validation)
        save_final_json_file(final_json)

        # Show one short success message, but do not print the full JSON.
        print("Done. File processed and saved in the outputs folder.")
    except Exception as error:
        # Show a simple error message so the output is easier to read.
        print(error)


def normalize_value_for_comparison(value):
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)

    value = str(value or "").casefold()
    value = re.sub(r"[\s\-:/.,|]+", "", value)
    return value


def normalize_date_value_for_comparison(value):
    value = str(value or "").strip()
    patterns = [
        r"^((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})$",
        r"^(\d{1,2})[-/.](\d{1,2})[-/.]((?:19|20)\d{2})$",
    ]

    for index, pattern in enumerate(patterns):
        match = re.match(pattern, value)
        if not match:
            continue

        if index == 0:
            year, month, day = match.groups()
        else:
            day, month, year = match.groups()

        return f"{year}{int(month):02d}{int(day):02d}"

    return normalize_value_for_comparison(value)


def normalize_text_tokens(value):
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)

    value = str(value or "").casefold()
    value = re.sub(r"[^a-z0-9\u0900-\u097F ]+", " ", value)
    return [token for token in value.split() if token]


def token_similarity_percent(extracted_value, expected_value):
    extracted_tokens = normalize_text_tokens(extracted_value)
    expected_tokens = normalize_text_tokens(expected_value)

    if not extracted_tokens or not expected_tokens:
        return 0

    extracted_set = set(extracted_tokens)
    expected_set = set(expected_tokens)
    overlap_score = len(extracted_set & expected_set) / len(expected_set)
    sequence_score = SequenceMatcher(None, " ".join(extracted_tokens), " ".join(expected_tokens)).ratio()

    return round(max(overlap_score, sequence_score) * 100, 2)


def compare_field_value(field_name, extracted_value, expected_value):
    fuzzy_fields = {
        "name",
        "hindi_name",
        "address",
        "hindi_address",
        "hindi_address_lines",
        "father_name",
        "husband_name",
        "care_of",
        "hindi_father_name",
        "hindi_husband_name",
        "hindi_care_of",
        "father_name",
        "hindi_father_name",
    }

    if field_name in fuzzy_fields:
        similarity_percent = token_similarity_percent(extracted_value, expected_value)
        threshold = 65 if field_name == "address" else 80

        return similarity_percent >= threshold, similarity_percent

    if field_name == "date_of_birth":
        is_match = (
            normalize_date_value_for_comparison(extracted_value)
            == normalize_date_value_for_comparison(expected_value)
        )
        return is_match, 100 if is_match else 0

    is_match = normalize_value_for_comparison(extracted_value) == normalize_value_for_comparison(expected_value)
    return is_match, 100 if is_match else 0


def ground_truth_value_is_present(value):
    if value is None or value is False:
        return False

    if isinstance(value, str) and value.strip() == "":
        return False

    if value == "" or value == [] or value == {}:
        return False

    return True


def compare_with_ground_truth(extracted_data, ground_truth):
    field_results = {}
    matched_fields = 0
    total_fields = 0

    for field_name, expected_value in ground_truth.items():
        extracted_value = extracted_data.get(field_name, "")
        used_for_accuracy = ground_truth_value_is_present(expected_value)

        if not used_for_accuracy:
            field_results[field_name] = {
                "extracted_value": extracted_value,
                "ground_truth_value": expected_value,
                "match": False,
                "used_for_accuracy": False,
                "reason": "ground truth value not present",
            }
            continue

        total_fields += 1
        is_match, similarity_percent = compare_field_value(field_name, extracted_value, expected_value)

        if is_match:
            matched_fields += 1

        field_results[field_name] = {
            "extracted_value": extracted_value,
            "ground_truth_value": expected_value,
            "match": is_match,
            "used_for_accuracy": True,
            "similarity_percent": similarity_percent,
        }

    accuracy = (matched_fields / total_fields * 100) if total_fields else 0

    return {
        "matched_fields": matched_fields,
        "total_fields": total_fields,
        "accuracy_percent": round(accuracy, 2),
        "field_results": field_results,
    }


def make_readable_comparison(comparison):
    readable_fields = {}

    for field_name, field_result in comparison["field_results"].items():
        readable_field = {
            "expected": field_result["ground_truth_value"],
            "extracted": field_result["extracted_value"],
            "match": field_result["match"],
            "used_for_accuracy": field_result["used_for_accuracy"],
        }

        if "similarity_percent" in field_result:
            readable_field["similarity_percent"] = field_result["similarity_percent"]

        if "reason" in field_result:
            readable_field["reason"] = field_result["reason"]

        readable_fields[field_name] = readable_field

    return {
        "accuracy_percent": comparison["accuracy_percent"],
        "matched_fields": comparison["matched_fields"],
        "total_fields": comparison["total_fields"],
        "fields": readable_fields,
    }


def load_ground_truth_for_image(image_path, ground_truth_folder):
    ground_truth_path = ground_truth_folder / f"{image_path.stem}.json"

    if not ground_truth_path.is_file():
        return ground_truth_path, {}

    with ground_truth_path.open("r", encoding="utf-8") as json_file:
        return ground_truth_path, json.load(json_file)


def get_clean_ocr_lines(text):
    lines = []

    for line in text.splitlines():
        line = " ".join(line.strip().split())
        if line:
            lines.append(line)

    return lines


def text_has_devanagari(text):
    return re.search(r"[\u0900-\u097F]", text) is not None


def line_is_noise(line):
    normalized = line.casefold()

    if any(word in normalized for word in aadhaar_footer_words):
        return True

    if "@" in normalized:
        return True

    if re.fullmatch(r"[\W\d_]+", line):
        return True

    return False


def find_aadhaar_number(text):
    for match in re.finditer(r"(?<!\d)(\d{4})[\s-]*(\d{4})[\s-]*(\d{4})(?!\d)", text):
        number = " ".join(match.groups())
        digits = re.sub(r"\D", "", number)

        if digits.startswith(("0", "1")):
            continue

        return number

    return ""


def find_vid(text):
    match = re.search(r"(?<!\d)(\d{4})[\s-]*(\d{4})[\s-]*(\d{4})[\s-]*(\d{4})(?!\d)", text)

    if match:
        return " ".join(match.groups())

    return ""


def find_date_of_birth(text):
    patterns = [
        r"(?:DOB|Date\s*of\s*Birth|Birth)\s*[:：-]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
        r"(?:DOB|Date\s*of\s*Birth|Birth)\s*[:：-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
        r"(?<!\d)(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})(?!\d)",
        r"(?<!\d)(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})(?!\d)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(1))

    return ""


def find_year_of_birth(text):
    match = re.search(r"(?:YOB|Year\s*of\s*Birth|Birth\s*Year)\s*[:：-]?\s*((?:19|20)\d{2})", text, flags=re.IGNORECASE)

    if match:
        return match.group(1)

    return ""


def find_pan_number(text):
    normalized_text = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    match = re.search(r"[A-Z]{5}\d{4}[A-Z]", normalized_text)
    return match.group(0) if match else ""


def normalize_date_for_ground_truth(date_text):
    date_text = re.sub(r"\s*([/.-])\s*", r"\1", str(date_text or "").strip())

    match = re.search(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})(?!\d)", date_text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    match = re.search(r"(?<!\d)((?:19|20)\d{2})[/-](\d{1,2})[/-](\d{1,2})(?!\d)", date_text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return date_text


def find_pan_date_of_birth(text):
    label_pattern = r"(?:Date\s*of\s*Birth|DOB|जन्म\s*की\s*तारीख)"
    patterns = [
        rf"{label_pattern}\s*[:：/-]?\s*(\d{{1,2}}[/-]\d{{1,2}}[/-](?:19|20)\d{{2}})",
        rf"{label_pattern}\s*[:：/-]?\s*((?:19|20)\d{{2}}[/-]\d{{1,2}}[/-]\d{{1,2}})",
        r"(?<!\d)(\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2})(?!\d)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return normalize_date_for_ground_truth(match.group(1))

    return ""


def find_card_issue_date_text(text):
    candidates = re.findall(r"(?<!\d)(\d{8})(?!\d)", text)

    for candidate in candidates:
        if not candidate.startswith(("19", "20")):
            return candidate

    return ""


def line_has_pan_noise(line):
    return re.search(
        r"PAN|Permanent|Account|Number|Income|Tax|Department|Govt|Government|India|Signature|Date|Birth|QR|Card",
        line,
        flags=re.IGNORECASE,
    ) is not None


def clean_pan_name(value):
    value = re.sub(r"[^A-Za-z .']", " ", str(value))
    words = [word for word in value.split() if len(word) > 1]
    return " ".join(words[:4])


def find_labeled_pan_value(lines, labels, allow_devanagari=False):
    label_pattern = "|".join(re.escape(label) for label in labels)

    for index, line in enumerate(lines):
        if re.search(label_pattern, line, flags=re.IGNORECASE):
            for candidate in lines[index + 1:index + 4]:
                if allow_devanagari:
                    cleaned = clean_hindi_text(candidate)
                    if cleaned:
                        return cleaned
                elif is_possible_name_line(candidate):
                    return clean_pan_name(candidate)

    return ""


def find_pan_english_names(lines):
    candidates = []

    for line in lines:
        if line_has_pan_noise(line) or text_has_devanagari(line):
            continue

        if find_pan_number(line) or re.search(r"\d|/", line):
            continue

        if is_possible_name_line(line):
            candidates.append(clean_pan_name(line))

    return candidates


def find_pan_hindi_values(lines):
    values = []

    for line in lines:
        if not text_has_devanagari(line) or line_is_noise(line):
            continue

        cleaned = clean_hindi_text(line)

        if cleaned and cleaned not in {"नाम", "पिता का नाम", "जन्म की तारीख", "हस्ताक्षर", "भारत सरकार", "आयकर विभाग"}:
            values.append(cleaned)

    return values


def find_gender(text):
    if re.search(r"\b(female|femaie|woman)\b", text, flags=re.IGNORECASE):
        return "FEMALE"

    if re.search(r"\b(male|maie|man)\b", text, flags=re.IGNORECASE):
        return "MALE"

    if "महिला" in text:
        return "FEMALE"

    if "पुरुष" in text:
        return "MALE"

    return ""


def find_pincode(text):
    ignored_numbers = {re.sub(r"\D", "", find_aadhaar_number(text)), re.sub(r"\D", "", find_vid(text)), "1947"}
    candidates = re.findall(r"(?<!\d)([1-9]\d{5})(?!\d)", text)

    for candidate in reversed(candidates):
        if candidate not in ignored_numbers:
            return candidate

    return ""


def find_relationship(text):
    patterns = [
        ("care_of", "C/O", r"\b(?:C/O|Care\s*Of)\s*[:：-]?\s*([A-Za-z][A-Za-z .']+)"),
        ("father_name", "Father", r"\b(?:Father|Father\s*Name|S/O)\s*[:：-]?\s*([A-Za-z][A-Za-z .']+)"),
        ("husband_name", "Husband", r"\b(?:Husband|Husband\s*Name|W/O)\s*[:：-]?\s*([A-Za-z][A-Za-z .']+)"),
    ]
    result = {
        "relationship_label": "",
        "care_of": "",
        "father_name": "",
        "husband_name": "",
    }

    for field_name, label, pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            result["relationship_label"] = label
            result[field_name] = clean_person_name(match.group(1))
            return result

    return result


def find_hindi_relationship(lines):
    result = {
        "hindi_relationship_label": "",
        "hindi_care_of": "",
        "hindi_father_name": "",
        "hindi_husband_name": "",
    }
    label_map = {
        "मार्फत": "hindi_care_of",
        "पिता": "hindi_father_name",
        "पुत्र": "hindi_father_name",
        "पति": "hindi_husband_name",
        "पत्नी": "hindi_husband_name",
    }

    for line in lines:
        if not text_has_devanagari(line):
            continue

        match = re.search(r"(मार्फत|पिता|पुत्र|पति|पत्नी)\s*[:：-]?\s*([\u0900-\u097F ]+)", line)
        if not match:
            continue

        label = match.group(1)
        value = clean_hindi_text(match.group(2))

        if value:
            result["hindi_relationship_label"] = label
            result[label_map[label]] = value
            return result

    return result


def clean_person_name(value):
    value = re.split(r"\s{2,}|,|\n|Address|पता|S/O|W/O|C/O", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = re.sub(r"[^A-Za-z .']", " ", value)
    words = value.split()
    junk_prefixes = {"O", "OC", "ID", "NO", "UID", "VID", "DOB", "TO", "OF"}

    while len(words) > 2 and words[0].upper() in junk_prefixes:
        words = words[1:]

    if len(words) > 2 and len(words[0]) <= 3 and words[0].isupper():
        words = words[1:]

    return " ".join(words)


def clean_hindi_text(value):
    value = re.sub(r"[^\u0900-\u097F ]", " ", str(value))
    value = re.sub(r"\b(?:पता|पिता|पुत्र|मार्फत|पति|पत्नी)\b", " ", value)
    return " ".join(value.split())


def find_hindi_name(lines):
    for line in lines:
        if text_has_devanagari(line) and not line_is_noise(line):
            cleaned = re.sub(r"[^\u0900-\u097F ]", " ", line)
            cleaned = " ".join(cleaned.split())

            if cleaned:
                return cleaned

    return ""


def find_front_name(lines):
    for index, line in enumerate(lines):
        if re.search(r"\b(DOB|Date\s*of\s*Birth|YOB|Male|Female)\b", line, flags=re.IGNORECASE):
            for candidate in reversed(lines[max(0, index - 3):index]):
                if is_possible_name_line(candidate):
                    return clean_person_name(candidate)

    for line in lines:
        if is_possible_name_line(line):
            return clean_person_name(line)

    return ""


def is_possible_name_line(line):
    if line_is_noise(line) or text_has_devanagari(line):
        return False

    if re.search(r"\d|@|/|www|uidai|gov|india|bharat|sample|photo", line, flags=re.IGNORECASE):
        return False

    if re.search(r"\b(DOB|YOB|Male|Female|Address|Father|Husband|Government|India)\b", line, flags=re.IGNORECASE):
        return False

    words = re.findall(r"[A-Za-z]+", line)
    long_words = [word for word in words if len(word) > 1]
    return 2 <= len(long_words) <= 4


def remove_duplicate_pincode(address, pincode):
    if not pincode:
        return address

    seen = False

    def replace_match(match):
        nonlocal seen

        if seen:
            return ""

        seen = True
        return match.group(0)

    return re.sub(rf"(?<!\d){re.escape(pincode)}(?!\d)", replace_match, address)


def find_address(lines, aadhaar_number, pincode, relationship):
    address_lines = find_address_lines_near_pincode(lines, pincode)

    if not address_lines:
        address_lines = []
        start_collecting = False

        for line in lines:
            if line_is_noise(line) or text_has_devanagari(line):
                continue

            line_without_aadhaar = line.replace(aadhaar_number, "").strip()
            if not line_without_aadhaar:
                continue

            if re.search(r"\b(Address|पता|Father|Husband|S/O|W/O|C/O|Care\s*Of)\b", line_without_aadhaar, flags=re.IGNORECASE):
                start_collecting = True
                value = re.sub(
                    r".*?\b(?:Address|पता|Father|Husband|S/O|W/O|C/O|Care\s*Of)\b\s*[:：-]?",
                    "",
                    line_without_aadhaar,
                    flags=re.IGNORECASE,
                ).strip()
                if value:
                    address_lines.append(value)
                continue

            if pincode and pincode in line_without_aadhaar:
                start_collecting = True

            if start_collecting:
                address_lines.append(line_without_aadhaar)

                if pincode and pincode in line_without_aadhaar:
                    break

    cleaned_lines = []

    for line in address_lines:
        line = re.sub(r"\b(?:Address|पता)\b\s*[:：-]?", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\b(?:Father|Husband|S/O|W/O|C/O|Care\s*Of)\b\s*[:：-]?\s*[A-Za-z .']+", "", line, flags=re.IGNORECASE)
        line = line.replace(aadhaar_number, "")

        for relationship_value in relationship.values():
            if relationship_value and relationship_value not in ["Father", "Husband", "C/O"]:
                line = line.replace(relationship_value, "")

        if pincode:
            line = line.replace(pincode, f" {pincode} ")
        line = re.sub(r"[^A-Za-z0-9\u0900-\u097F ,.-]", " ", line)
        line = " ".join(line.split(" "))
        line = " ".join(line.split())

        if line and not line_is_noise(line):
            cleaned_lines.append(line)

    address = " ".join(dict.fromkeys(cleaned_lines))
    address = remove_duplicate_pincode(address, pincode)

    if pincode and pincode not in address:
        address = f"{address} {pincode}".strip()

    return address


def find_hindi_address_lines(lines, pincode, hindi_relationship):
    selected_lines = []
    started = False

    for line in lines:
        has_hindi = text_has_devanagari(line)
        has_pincode = bool(pincode and pincode in line)

        if not has_hindi and not has_pincode:
            continue

        if line_is_noise(line) and not has_pincode:
            continue

        if "पता" in line:
            started = True
            selected_lines.append("पता:")
            remainder = clean_hindi_text(re.sub(r".*?पता\s*[:：-]?", "", line))
            if remainder:
                selected_lines.append(remainder)
            continue

        if started or (pincode and pincode in line):
            selected_lines.append(line)

        if pincode and pincode in line:
            break

    if not selected_lines and pincode:
        for index, line in enumerate(lines):
            if pincode not in line:
                continue

            nearby_lines = lines[max(0, index - 4):index + 1]
            selected_lines = [
                line for line in nearby_lines
                if (text_has_devanagari(line) or pincode in line) and not line_is_noise(line)
            ]
            break

    cleaned_lines = []
    for line in selected_lines:
        if line.strip() == "पता:":
            cleaned_lines.append("पता:")
            continue

        cleaned = line
        cleaned = re.sub(r"[^\u0900-\u097F0-9A-Za-z ,.-]", " ", cleaned)
        cleaned = " ".join(cleaned.split())

        if cleaned and cleaned not in cleaned_lines:
            cleaned_lines.append(cleaned)

    return cleaned_lines


def join_hindi_address_lines(lines):
    address_parts = [
        line for line in lines
        if line.strip() != "पता:" and not re.search(r"^(मार्फत|पिता|पुत्र|पति|पत्नी)\s*[:：-]?", line)
    ]
    return " ".join(address_parts)


def find_address_lines_near_pincode(lines, pincode):
    if not pincode:
        return []

    for index, line in enumerate(lines):
        if pincode not in line:
            continue

        start_index = max(0, index - 4)

        for candidate_index in range(index, start_index - 1, -1):
            if re.search(r"\b(Address|पता|Father|Husband|S/O|W/O|C/O|Care\s*Of)\b", lines[candidate_index], flags=re.IGNORECASE):
                start_index = candidate_index
                break

        return [
            line for line in lines[start_index:index + 1]
            if not line_is_noise(line) and not text_has_devanagari(line)
        ]

    return []


def infer_aadhaar_document_type(text, image_path):
    file_name = image_path.stem.casefold()
    front_score = 0
    back_score = 0

    if re.search(r"\b(DOB|Date\s*of\s*Birth|YOB|Male|Female)\b", text, flags=re.IGNORECASE):
        front_score += 2

    if find_gender(text) or find_date_of_birth(text) or find_year_of_birth(text):
        front_score += 1

    if re.search(r"\b(Address|पता|Pincode|Father|Husband|S/O|W/O|C/O|Care\s*Of)\b", text, flags=re.IGNORECASE):
        back_score += 2

    if find_pincode(text):
        back_score += 1

    if back_score > front_score:
        return "aadhaar_back"

    if front_score > back_score:
        return "aadhaar_front"

    if "front" in file_name:
        return "aadhaar_front"

    if "back" in file_name:
        return "aadhaar_back"

    return "aadhaar_front"


def get_image_side(image_path):
    file_name = image_path.stem.casefold()

    if "front" in file_name:
        return "front"

    if "back" in file_name:
        return "back"

    return "unknown"


def get_image_quality_category(image_path):
    file_name = image_path.stem.casefold()

    for category in image_quality_categories:
        if category in file_name:
            return category

    return "unknown"


def extract_aadhaar_fields_from_text(text, image_path):
    if not text.strip() or not find_aadhaar_number(text):
        return "", {}

    lines = get_clean_ocr_lines(text)
    document_type = infer_aadhaar_document_type(text, image_path)
    aadhaar_number = find_aadhaar_number(text)
    vid = find_vid(text)

    if document_type == "aadhaar_back":
        pincode = find_pincode(text)
        relationship = find_relationship(text)
        hindi_relationship = find_hindi_relationship(lines)
        hindi_address_lines = find_hindi_address_lines(lines, pincode, hindi_relationship)
        extracted_data = {
            "aadhaar_number": aadhaar_number,
            "address": find_address(lines, aadhaar_number, pincode, relationship),
            "pincode": pincode,
            "vid": vid,
            **relationship,
            **hindi_relationship,
            "hindi_address": join_hindi_address_lines(hindi_address_lines),
            "hindi_address_lines": hindi_address_lines,
        }
    else:
        date_of_birth = find_date_of_birth(text)
        extracted_data = {
            "aadhaar_number": aadhaar_number,
            "name": find_front_name(lines),
            "gender": find_gender(text),
            "vid": vid,
            "hindi_name": find_hindi_name(lines),
            "date_of_birth": date_of_birth,
            "year_of_birth": find_year_of_birth(text) if not date_of_birth else "",
        }

    return document_type, extracted_data


def make_aadhaar_classification(document_type):
    schema = aadhaar_back_schema if document_type == "aadhaar_back" else aadhaar_front_schema
    matched_fields = list(schema.keys())

    return {
        "document_type": document_type,
        "schema": schema,
        "confidence": 1,
        "confidence_percent": 100,
        "confidence_level": describe_confidence_level(1),
        "matched_fields": matched_fields,
        "missing_fields": [],
        "matched_count": len(matched_fields),
        "total_fields": len(matched_fields),
        "all_scores": [],
        "score_gap": 0,
    }


def make_pan_classification():
    return {
        "document_type": "pan_card",
        "schema": pan_card_schema,
        "confidence": 1,
        "confidence_percent": 100,
        "confidence_level": describe_confidence_level(1),
        "matched_fields": list(pan_card_schema.keys()),
        "missing_fields": [],
        "matched_count": len(pan_card_schema),
        "total_fields": len(pan_card_schema),
        "all_scores": [],
        "score_gap": 0,
    }


def extracted_data_has_value(extracted_data):
    return any(str(value or "").strip() for value in extracted_data.values())


def extract_pan_fields_from_text(text, image_path):
    if not text.strip():
        return "", {}

    lines = get_clean_ocr_lines(text)
    pan_number = find_pan_number(text)

    if not pan_number and "pan" not in text.casefold() and "income tax" not in text.casefold():
        return "", {}

    english_names = find_pan_english_names(lines)
    hindi_values = find_pan_hindi_values(lines)
    extracted_data = {
        "pan_number": pan_number,
        "name": find_labeled_pan_value(lines, ["Name", "नाम"]) or (english_names[0] if english_names else ""),
        "hindi_name": find_labeled_pan_value(lines, ["नाम"], allow_devanagari=True) or (hindi_values[0] if hindi_values else ""),
        "father_name": find_labeled_pan_value(lines, ["Father's Name", "Father Name", "पिता का नाम"])
        or (english_names[1] if len(english_names) > 1 else ""),
        "hindi_father_name": find_labeled_pan_value(lines, ["पिता का नाम"], allow_devanagari=True)
        or (hindi_values[1] if len(hindi_values) > 1 else ""),
        "date_of_birth": find_pan_date_of_birth(text),
        "signature_present": bool(re.search(r"Signature|हस्ताक्षर", text, flags=re.IGNORECASE)),
        "card_issue_date_text": find_card_issue_date_text(text),
    }

    return "pan_card", extracted_data


def process_image_with_model(image_path, model_name, fallback_extractor, make_fallback_classification):
    text = extract_text_from_image(image_path, model_name=model_name)
    classification = choose_document_type_from_text(text)

    if classification["schema"] is not None:
        mapped_fields = extract_field_values_using_schema(text, classification["schema"])
    else:
        mapped_fields = {}

    fallback_document_type, fallback_fields = fallback_extractor(text, image_path)

    if fallback_document_type and (classification["document_type"] == "unknown" or not extracted_data_has_value(mapped_fields)):
        classification = make_fallback_classification(fallback_document_type)
        mapped_fields = fallback_fields
    elif fallback_fields:
        mapped_fields = {
            **mapped_fields,
            **{field: value for field, value in fallback_fields.items() if value},
        }

    validation = validate_extracted_fields(classification, mapped_fields)

    return {
        "extracted_data": validation["extracted_data"],
        "validation": {
            "summary": validation["validation_summary"],
            "field_results": validation["validation_results"],
        },
        "comparison_with_ground_truth": {},
        "classification": {
            "document_type": classification["document_type"],
            "confidence_percent": classification["confidence_percent"],
            "confidence_level": classification["confidence_level"],
        },
        "raw_text": text,
    }


def process_aadhaar_image_with_model(image_path, model_name):
    return process_image_with_model(
        image_path,
        model_name,
        extract_aadhaar_fields_from_text,
        make_aadhaar_classification,
    )


def process_pan_image_with_model(image_path, model_name):
    return process_image_with_model(
        image_path,
        model_name,
        extract_pan_fields_from_text,
        lambda _document_type: make_pan_classification(),
    )


def list_document_images(images_folder):
    return sorted(
        path for path in images_folder.iterdir()
        if path.is_file() and path.suffix.lower() in image_extensions
    )


def process_document_image_folder(
    document_name,
    images_folder,
    ground_truth_folder,
    process_model,
    excel_file_name,
):
    model_names = get_available_ocr_models()
    excel_rows = []
    json_outputs = []

    for image_path in list_document_images(images_folder):
        ground_truth_path, ground_truth = load_ground_truth_for_image(image_path, ground_truth_folder)
        model_outputs = {}
        excel_row = {
            "image address": str(image_path),
            "document side": get_image_side(image_path),
            "image quality category": get_image_quality_category(image_path),
        }

        for model_name in model_names:
            try:
                model_result = process_model(image_path, model_name)
                comparison = compare_with_ground_truth(model_result["extracted_data"], ground_truth)
                model_outputs[model_name] = {
                    "extracted_data": model_result["extracted_data"],
                    "comparison_with_ground_truth": make_readable_comparison(comparison),
                }
                excel_row[model_name] = comparison["accuracy_percent"]
            except Exception as error:
                comparison = compare_with_ground_truth({}, ground_truth)
                model_outputs[model_name] = {
                    "extracted_data": {},
                    "comparison_with_ground_truth": make_readable_comparison(comparison),
                    "error": str(error),
                }
                excel_row[model_name] = comparison["accuracy_percent"]

        final_json = {
            "image": {
                "address": str(image_path),
                "ground_truth_address": str(ground_truth_path),
                "side": get_image_side(image_path),
                "quality": get_image_quality_category(image_path),
            },
            "ground_truth": ground_truth,
            "models": model_outputs,
        }
        json_outputs.append(save_document_json_file(image_path, final_json, document_name))
        excel_rows.append(excel_row)

    excel_output = save_accuracy_excel(
        excel_rows,
        model_names,
        file_name=excel_file_name,
        output_subfolder=document_name,
    )

    return {
        "processed_images": len(excel_rows),
        "json_outputs": json_outputs,
        "excel_output": excel_output,
    }


def process_aadhaar_folder():
    return process_document_image_folder(
        "aadhaar",
        aadhaar_images_folder,
        aadhaar_ground_truth_folder,
        process_aadhaar_image_with_model,
        "aadhaar_model_accuracy.xlsx",
    )


def process_pan_folder():
    return process_document_image_folder(
        "pan",
        pan_images_folder,
        pan_ground_truth_folder,
        process_pan_image_with_model,
        "pan_model_accuracy.xlsx",
    )


def main():
    if len(sys.argv) < 2:
        print("Please enter a file name from the uploads folder, or use --aadhaar-batch / --pan-batch.")
        return

    if sys.argv[1] == "--aadhaar-batch":
        result = process_aadhaar_folder()
        print(f"Done. Processed {result['processed_images']} Aadhaar images.")
        print(f"Excel saved at: {result['excel_output']}")
        return

    if sys.argv[1] == "--pan-batch":
        result = process_pan_folder()
        print(f"Done. Processed {result['processed_images']} PAN images.")
        print(f"Excel saved at: {result['excel_output']}")
        return

    run_document_processing(sys.argv[1])


if __name__ == "__main__":
    main()
