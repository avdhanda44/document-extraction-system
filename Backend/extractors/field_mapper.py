from functools import lru_cache

import regex as fuzzy_regex


def get_labels_for_field(label_or_labels):
    # Some fields have one label.
    # Some fields have many labels, like English + Hindi labels for Aadhaar.
    if isinstance(label_or_labels, list):
        return label_or_labels

    return [label_or_labels]


@lru_cache(maxsize=256)
def remove_colon_from_label(label):
    # Remove common label separators because extracted text may or may not keep them.
    label = fuzzy_regex.sub(r"[:：|._-]+", " ", label)
    return " ".join(label.split())


def clean_extracted_value(value):
    # Remove extra spaces and separators from the extracted value.
    # Example: "  : Rahul Verma  " becomes "Rahul Verma".
    value = " ".join(value.split())
    value = value.strip(" :-|\t\n")

    return value


@lru_cache(maxsize=128)
def get_clean_lines(extracted_text):
    lines = []

    for line in extracted_text.splitlines():
        clean_line = clean_extracted_value(line)
        if clean_line:
            lines.append(clean_line)

    return tuple(lines)


def extract_first_aadhaar_number(extracted_text):
    match = fuzzy_regex.search(r"(?<!\d)(\d{4}\s+\d{4}\s+\d{4})(?!\d)", extracted_text)

    if match:
        return match.group(1)

    match = fuzzy_regex.search(r"(?<!\d)(\d{12})(?!\d)", extracted_text)

    if match:
        value = match.group(1)
        return f"{value[:4]} {value[4:8]} {value[8:]}"

    return ""


def extract_first_vid(extracted_text):
    match = fuzzy_regex.search(r"(?<!\d)(\d{4}\s+\d{4}\s+\d{4}\s+\d{4})(?!\d)", extracted_text)

    if match:
        return match.group(1)

    match = fuzzy_regex.search(r"(?<!\d)(\d{16})(?!\d)", extracted_text)

    if match:
        value = match.group(1)
        return f"{value[:4]} {value[4:8]} {value[8:12]} {value[12:]}"

    return ""


def extract_first_pincode(extracted_text):
    stop_match = fuzzy_regex.search(
        r"\b(?:P\.?\s*O\.?\s*Box|help@|www\.|Bengaluru|1800)\b",
        extracted_text,
        flags=fuzzy_regex.IGNORECASE,
    )
    address_area = extracted_text[: stop_match.start()] if stop_match else extracted_text
    aadhaar_number = extract_first_aadhaar_number(address_area)
    address_area = address_area.replace(aadhaar_number, " ") if aadhaar_number else address_area

    matches = fuzzy_regex.findall(r"(?<!\d)([1-9]\d{5})(?!\d)", address_area)

    return matches[-1] if matches else ""


def extract_text_after_any_label(extracted_text, labels):
    label_pattern = "|".join(fuzzy_regex.escape(label) for label in labels)
    pattern = rf"(?:{label_pattern})\s*[:：]?\s*(.+)"
    match = fuzzy_regex.search(pattern, extracted_text, flags=fuzzy_regex.IGNORECASE)

    if match:
        return clean_extracted_value(match.group(1).splitlines()[0])

    return ""


def extract_name_from_aadhaar_front(extracted_text):
    ignored_phrases = {
        "भारत सरकार",
        "government of india",
        "sample photo",
    }
    lines = get_clean_lines(extracted_text)

    for line in lines:
        if line.casefold() in ignored_phrases:
            continue

        if fuzzy_regex.fullmatch(r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3}", line):
            return line

    return ""


def is_noisy_aadhaar_hindi_name(value):
    value = value or ""

    if not value:
        return True

    noisy_values = {
        "भारत सरकार",
        "भारतीय विशिष्ट पहचान प्राधिकरण",
        "आधार",
    }
    noisy_markers = ["जन्म", "पुरुष", "महिला", "आम आदमी", "अधिकार"]

    return value in noisy_values or any(marker in value for marker in noisy_markers) or len(value.split()) > 4


def extract_hindi_name_from_aadhaar_front(extracted_text):
    lines = get_clean_lines(extracted_text)

    for index, line in enumerate(lines):
        if fuzzy_regex.search(r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3}", line):
            for previous_line in reversed(lines[:index]):
                if fuzzy_regex.search(r"\p{Devanagari}", previous_line):
                    if previous_line in {"भारत सरकार", "भारतीय विशिष्ट पहचान प्राधिकरण"}:
                        continue

                    if any(marker in previous_line for marker in ["जन्म", "पुरुष", "महिला", "आधार"]):
                        continue

                    return previous_line

    return ""


def normalize_aadhaar_ocr_digits(text):
    translation = str.maketrans({
        "०": "0",
        "१": "1",
        "२": "2",
        "३": "3",
        "४": "4",
        "५": "5",
        "६": "6",
        "७": "7",
        "८": "8",
        "९": "9",
    })
    return str(text or "").translate(translation)


def normalize_aadhaar_front_date(date_text):
    text = normalize_aadhaar_ocr_digits(date_text)
    text = fuzzy_regex.sub(r"(?i)[il|]", "1", text)
    text = fuzzy_regex.sub(r"\s+", "", text)
    text = text.replace("-/", "-1").replace("./", ".1")
    text = fuzzy_regex.sub(r"(?<=\d)/(?!\d{2,4}\b)", "1", text)

    match = fuzzy_regex.search(r"(\d{4})[-/.](\d{2})[-/.](\d{2})", text)
    if match:
        return "-".join(match.groups())

    match = fuzzy_regex.search(r"(\d{2})[-/.](\d{2})[-/.](\d{4})", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    return ""


def extract_aadhaar_front_date(extracted_text):
    label_match = fuzzy_regex.search(
        r"(?:DOB|D\.O\.B|Date\s+of\s+Birth|जन्म\s*(?:तिथि|तारीख))\s*[:：/]?\s*([^\n]+)",
        extracted_text,
        flags=fuzzy_regex.IGNORECASE,
    )

    if label_match:
        normalized_date = normalize_aadhaar_front_date(label_match.group(1))
        if normalized_date:
            return normalized_date

    return normalize_aadhaar_front_date(extracted_text)


def extract_aadhaar_gender(extracted_text):
    if fuzzy_regex.search(r"\bFemale\b|महिला", extracted_text, flags=fuzzy_regex.IGNORECASE):
        return "Female"

    if fuzzy_regex.search(r"\bMale\b|पुरुष", extracted_text, flags=fuzzy_regex.IGNORECASE):
        return "Male"

    return ""


def extract_aadhaar_address_block(extracted_text):
    english_address = extract_english_aadhaar_address(extracted_text)

    if english_address:
        return english_address

    match = fuzzy_regex.search(
        r"(?:पता|Address)\s*[:：]\s*(.+?)(?=\bP\.?\s*O\.?\s*Box\b|help@|www\.|Bengaluru|1800|$)",
        extracted_text,
        flags=fuzzy_regex.IGNORECASE | fuzzy_regex.DOTALL,
    )

    if not match:
        return ""

    address = match.group(1)
    aadhaar_number = extract_first_aadhaar_number(address)

    if aadhaar_number:
        address = address.split(aadhaar_number, 1)[0]

    address = fuzzy_regex.sub(r"\b(?:S/O|C/O|W/O)\s*[:：]\s*[A-Za-z ]+", " ", address, flags=fuzzy_regex.IGNORECASE)
    address = fuzzy_regex.sub(r"(?:पुत्र|पिता|पति)\s*[:：]\s*[\p{Devanagari}\s]+(?=\d|[A-Za-z])", " ", address)
    address = fuzzy_regex.sub(r"\s+", " ", address)
    address = clean_extracted_value(address)

    pincode = extract_first_pincode(extracted_text)

    if pincode and pincode not in address:
        address = f"{address} {pincode}".strip()

    return address


def clean_english_address_line(line):
    line = fuzzy_regex.sub(r"[\p{Devanagari}]+", " ", line)
    line = fuzzy_regex.sub(r"\b(?:S/O|C/O|W/O)\s*[:：]\s*[A-Za-z .]+$", " ", line, flags=fuzzy_regex.IGNORECASE)
    line = fuzzy_regex.sub(r"\s+", " ", line)
    return clean_extracted_value(line)


def extract_english_aadhaar_address(extracted_text):
    lines = get_clean_lines(extracted_text)
    start_index = None

    for index, line in enumerate(lines):
        if fuzzy_regex.search(r"\b(?:S/O|C/O|W/O)\s*[:：]", line, flags=fuzzy_regex.IGNORECASE):
            start_index = index
            break

    if start_index is None:
        return ""

    address_lines = []

    for line in lines[start_index + 1 :]:
        if extract_first_aadhaar_number(line):
            break

        if fuzzy_regex.search(r"\b(?:P\.?\s*O\.?\s*Box|help@|www\.|Bengaluru|1800|UIDAI|UNIQUE IDENTIFICATION)\b", line, flags=fuzzy_regex.IGNORECASE):
            break

        cleaned_line = clean_english_address_line(line)

        if not cleaned_line:
            continue

        if not fuzzy_regex.search(r"[A-Za-z]", cleaned_line) and not fuzzy_regex.fullmatch(r"[1-9]\d{5}", cleaned_line):
            continue

        address_lines.append(cleaned_line)

        if fuzzy_regex.fullmatch(r"[1-9]\d{5}", cleaned_line):
            break

    if not address_lines:
        return ""

    return clean_extracted_value(" ".join(address_lines))


def extract_hindi_aadhaar_address_lines(extracted_text):
    lines = get_clean_lines(extracted_text)
    start_index = None

    for index, line in enumerate(lines):
        if line.startswith("पता"):
            start_index = index
            break

    if start_index is None:
        return []

    address_lines = []

    for index, line in enumerate(lines[start_index:], start=start_index):
        if index == start_index and line.startswith("पता"):
            address_lines.append("पता:")
            continue

        if fuzzy_regex.search(r"\b(?:S/O|C/O|W/O)\b", line, flags=fuzzy_regex.IGNORECASE):
            break

        if fuzzy_regex.search(r"\b(?:UNIQUE IDENTIFICATION|GOVERNMENT OF INDIA|help@|www\.|P\.?\s*O\.?\s*Box|Bengaluru|1800)\b", line, flags=fuzzy_regex.IGNORECASE):
            break

        if extract_first_aadhaar_number(line):
            break

        address_lines.append(line)

        if fuzzy_regex.fullmatch(r"[1-9]\d{5}", line):
            break

    return address_lines


def extract_hindi_aadhaar_address(extracted_text):
    lines = extract_hindi_aadhaar_address_lines(extracted_text)
    address_lines = []

    for line in lines:
        if line.startswith("पता") or line.startswith("पुत्र") or line.startswith("पिता"):
            continue

        line = fuzzy_regex.sub(r"[A-Za-z]+(?:[ ,.-]+[A-Za-z]+)*", " ", line)
        line = clean_extracted_value(line)

        if fuzzy_regex.fullmatch(r"[1-9]\d{5}", line) and any(line in item for item in address_lines):
            continue

        if line:
            address_lines.append(line)

    return clean_extracted_value(" ".join(address_lines))


def extract_aadhaar_relationship_name(extracted_text):
    match = fuzzy_regex.search(
        r"\b(S/O|C/O|W/O)\s*[:：]\s*([A-Za-z][A-Za-z .]+)",
        extracted_text,
        flags=fuzzy_regex.IGNORECASE,
    )

    if match:
        return match.group(1).upper(), clean_extracted_value(match.group(2))

    return "", ""


def extract_hindi_relationship_name(extracted_text):
    match = fuzzy_regex.search(
        r"(पुत्र|पिता|पति|पत्नी|मार्फत)\s*[:：]\s*([\p{Devanagari}\s]+?)(?=\s*\d|[A-Za-z]|$)",
        extracted_text,
    )

    if match:
        return match.group(1), clean_extracted_value(match.group(2))

    return "", ""


def is_noisy_aadhaar_relationship_value(value):
    value = value or ""
    noisy_markers = [
        "uidai",
        "help@",
        "www.",
        "P.O.",
        "Box No",
        "Bengaluru",
        "1947",
    ]

    return len(value.split()) > 6 or any(marker.casefold() in value.casefold() for marker in noisy_markers)


def enhance_aadhaar_fields(extracted_text, mapped_fields):
    if "aadhaar_number" in mapped_fields:
        mapped_fields["aadhaar_number"] = mapped_fields["aadhaar_number"] or extract_first_aadhaar_number(extracted_text)

    if "vid" in mapped_fields:
        mapped_fields["vid"] = extract_first_vid(mapped_fields["vid"]) or extract_first_vid(extracted_text) or mapped_fields["vid"]

    if "pincode" in mapped_fields:
        mapped_fields["pincode"] = mapped_fields["pincode"] or extract_first_pincode(extracted_text)

    if "address" in mapped_fields:
        english_address = extract_english_aadhaar_address(extracted_text)
        if english_address:
            mapped_fields["address"] = english_address
        else:
            mapped_fields["address"] = mapped_fields["address"] or extract_aadhaar_address_block(extracted_text)

    if "hindi_address_lines" in mapped_fields:
        mapped_fields["hindi_address_lines"] = mapped_fields["hindi_address_lines"] or extract_hindi_aadhaar_address_lines(extracted_text)

    if "hindi_address" in mapped_fields:
        mapped_fields["hindi_address"] = mapped_fields["hindi_address"] or extract_hindi_aadhaar_address(extracted_text)

    if "name" in mapped_fields:
        mapped_fields["name"] = mapped_fields["name"] or extract_name_from_aadhaar_front(extracted_text)

    if "hindi_name" in mapped_fields:
        if is_noisy_aadhaar_hindi_name(mapped_fields["hindi_name"]):
            mapped_fields["hindi_name"] = extract_hindi_name_from_aadhaar_front(extracted_text)

    if "date_of_birth" in mapped_fields:
        normalized_date = normalize_aadhaar_front_date(mapped_fields["date_of_birth"])
        mapped_fields["date_of_birth"] = normalized_date or extract_aadhaar_front_date(extracted_text) or mapped_fields["date_of_birth"]

    if "gender" in mapped_fields:
        mapped_fields["gender"] = extract_aadhaar_gender(extracted_text) or mapped_fields["gender"]

    relationship_label, relationship_name = extract_aadhaar_relationship_name(extracted_text)

    if relationship_name:
        if "relationship_label" in mapped_fields:
            mapped_fields["relationship_label"] = relationship_name

        target_fields = {
            "S/O": ("father_name",),
            "C/O": ("care_of",),
            "W/O": ("husband_name",),
        }.get(relationship_label, ("relationship_label",))

        for field_name in target_fields:
            if field_name in mapped_fields and (
                not mapped_fields[field_name]
                or is_noisy_aadhaar_relationship_value(mapped_fields[field_name])
            ):
                mapped_fields[field_name] = relationship_name

    hindi_relationship_label, hindi_relationship_name = extract_hindi_relationship_name(extracted_text)

    if hindi_relationship_name:
        if "hindi_relationship_label" in mapped_fields:
            mapped_fields["hindi_relationship_label"] = hindi_relationship_name

        target_fields = {
            "पुत्र": ("hindi_father_name",),
            "पिता": ("hindi_father_name",),
            "मार्फत": ("hindi_care_of",),
            "पति": ("hindi_husband_name",),
            "पत्नी": ("hindi_husband_name",),
        }.get(hindi_relationship_label, ("hindi_relationship_label",))

        for field_name in target_fields:
            if field_name in mapped_fields:
                mapped_fields[field_name] = hindi_relationship_name

    for field_name in ("hindi_relationship_label", "hindi_care_of", "hindi_father_name", "hindi_husband_name"):
        value = mapped_fields.get(field_name, "")
        if "help@" in value or "uidai" in value.casefold() or "Bengaluru" in value:
            mapped_fields[field_name] = hindi_relationship_name

    return mapped_fields


PAN_DIGIT_TRANSLATION = str.maketrans({
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
})


@lru_cache(maxsize=128)
def normalize_pan_ocr_text(text):
    return text.translate(PAN_DIGIT_TRANSLATION)


def normalize_pan_date(date_text):
    match = fuzzy_regex.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", date_text)

    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    match = fuzzy_regex.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", date_text)

    if match:
        return "-".join(match.groups())

    return ""


def extract_pan_number(extracted_text):
    normalized_text = normalize_pan_ocr_text(extracted_text).upper()
    match = fuzzy_regex.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", normalized_text)

    return match.group(0) if match else ""


def get_next_nonempty_line(lines, start_index):
    for line in lines[start_index + 1 :]:
        if line:
            return line

    return ""


def extract_pan_english_names(extracted_text):
    lines = get_clean_lines(extracted_text)
    name = ""
    father_name = ""

    for index, line in enumerate(lines):
        if line.casefold() == "name":
            candidate = get_next_nonempty_line(lines, index)
            if fuzzy_regex.fullmatch(r"[A-Z][A-Z ]{3,}", candidate):
                name = candidate.title()

        if "father" in line.casefold():
            candidate = get_next_nonempty_line(lines, index)

            if fuzzy_regex.fullmatch(r"\d{6,8}", candidate):
                candidate = get_next_nonempty_line(lines, index + 1)

            if fuzzy_regex.fullmatch(r"[A-Z][A-Z ]{3,}", candidate):
                candidate = candidate.title()
                if not father_name or len(candidate.split()) > len(father_name.split()):
                    father_name = candidate

    uppercase_names = [
        line
        for line in lines
        if fuzzy_regex.fullmatch(r"[A-Z][A-Z ]{3,}", line)
        and line not in {"INCOME TAX DEPARTMENT", "GOVT OF INDIA", "GOVT. OF INDIA"}
    ]

    if not name and uppercase_names:
        name = uppercase_names[0].title()

    if not father_name and len(uppercase_names) > 1:
        father_name = uppercase_names[1].title()

    return name, father_name


def extract_pan_hindi_names(extracted_text):
    lines = get_clean_lines(extracted_text)
    ignored_exact = {
        "वभाग",
        "आयकर",
        "भारत सरकार",
        "रत सरकार",
        "स्थायी",
        "लेखा",
        "संख्या",
        "कार्ड",
        "नाम",
        "पिता",
        "का",
        "जन्म",
        "तारीखा/",
        "तारीख/",
        "हस्ताक्षर",
    }
    ignored_markers = ["आयकर", "भारत सरकार", "स्थायी", "लेखा", "संख्या", "कार्ड", "जन्म", "तारीख", "हस्ताक्षर", "सत्पमेत", "सत्यमेव"]
    hindi_lines = []

    for line in lines:
        if not fuzzy_regex.search(r"\p{Devanagari}", line):
            continue

        if fuzzy_regex.search(r"[A-Za-z]", line):
            continue

        if line in ignored_exact or any(marker in line for marker in ignored_markers):
            continue

        if len(line) <= 2:
            continue

        hindi_lines.append(line)

    combined_lines = []
    index = 0

    while index < len(hindi_lines):
        line = hindi_lines[index]

        if index + 1 < len(hindi_lines) and len(line.split()) == 1 and len(hindi_lines[index + 1].split()) == 1:
            combined_lines.append(f"{line} {hindi_lines[index + 1]}")
            index += 2
            continue

        combined_lines.append(line)
        index += 1

    hindi_name = combined_lines[0] if combined_lines else ""
    hindi_father_name = combined_lines[1] if len(combined_lines) > 1 else ""

    return hindi_name, hindi_father_name


def extract_pan_issue_date(extracted_text):
    normalized_text = normalize_pan_ocr_text(extracted_text)
    match = fuzzy_regex.search(r"\b\d{8}\b", normalized_text)

    return match.group(0) if match else ""


def enhance_pan_fields(extracted_text, mapped_fields):
    normalized_text = normalize_pan_ocr_text(extracted_text)
    name, father_name = extract_pan_english_names(normalized_text)
    hindi_name, hindi_father_name = extract_pan_hindi_names(extracted_text)

    mapped_fields["pan_number"] = extract_pan_number(normalized_text) or mapped_fields.get("pan_number", "")
    mapped_fields["name"] = name or mapped_fields.get("name", "")
    mapped_fields["father_name"] = father_name or mapped_fields.get("father_name", "")
    mapped_fields["date_of_birth"] = normalize_pan_date(normalized_text) or mapped_fields.get("date_of_birth", "")
    mapped_fields["hindi_name"] = hindi_name or mapped_fields.get("hindi_name", "")
    mapped_fields["hindi_father_name"] = hindi_father_name or mapped_fields.get("hindi_father_name", "")
    mapped_fields["signature_present"] = bool(fuzzy_regex.search(r"signature|हस्ताक्षर", extracted_text, flags=fuzzy_regex.IGNORECASE))
    mapped_fields["card_issue_date_text"] = extract_pan_issue_date(normalized_text) or mapped_fields.get("card_issue_date_text", "")

    return mapped_fields


def extract_regex_value(extracted_text, pattern, flags=fuzzy_regex.IGNORECASE):
    match = fuzzy_regex.search(pattern, extracted_text, flags=flags)

    if match:
        return clean_extracted_value(match.group(1) if match.groups() else match.group(0))

    return ""


def extract_labeled_line_value(extracted_text, labels):
    lines = get_clean_lines(extracted_text)
    normalized_labels = [label.casefold() for label in labels]

    for index, line in enumerate(lines):
        line_text = line.casefold()

        for label in normalized_labels:
            if label not in line_text:
                continue

            after_label = line[line_text.find(label) + len(label):]
            after_label = clean_extracted_value(after_label)

            if after_label:
                return after_label

            return get_next_nonempty_line(lines, index)

    return ""


def normalize_slash_date(date_text):
    match = fuzzy_regex.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", date_text)

    if match:
        return "/".join(match.groups())

    return ""


def enhance_passbook_fields(extracted_text, mapped_fields):
    mapped_fields["ifsc"] = extract_regex_value(extracted_text, r"\b([A-Z]{4}0[A-Z0-9]{6})\b") or mapped_fields.get("ifsc", "")
    mapped_fields["micr"] = extract_regex_value(extracted_text, r"\b(\d{9})\b") or mapped_fields.get("micr", "")
    mapped_fields["pan_number"] = extract_pan_number(extracted_text) or mapped_fields.get("pan_number", "")
    mapped_fields["email"] = extract_regex_value(extracted_text, r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b") or mapped_fields.get("email", "")

    account_number = extract_labeled_line_value(extracted_text, ["Account No.", "Account Number", "A/c No", "Account No"])
    account_number = extract_regex_value(account_number, r"\b(\d{10,18})\b", flags=0) or extract_regex_value(extracted_text, r"\b(\d{10,18})\b", flags=0)
    mapped_fields["account_number"] = account_number or mapped_fields.get("account_number", "")

    cif_number = extract_labeled_line_value(extracted_text, ["CIF Number", "CIF"])
    mapped_fields["cif_number"] = extract_regex_value(cif_number, r"\b(\d{6,12})\b", flags=0) or mapped_fields.get("cif_number", "")

    branch_code = extract_labeled_line_value(extracted_text, ["Branch Code", "Code"])
    mapped_fields["branch_code"] = extract_regex_value(branch_code, r"\b(\d{3,8})\b", flags=0) or mapped_fields.get("branch_code", "")

    nom_reg_no = extract_labeled_line_value(extracted_text, ["Nom Reg No", "Nomination Registration Number"])
    mapped_fields["nom_reg_no"] = extract_regex_value(nom_reg_no, r"\b(\d{5,14})\b", flags=0) or mapped_fields.get("nom_reg_no", "")

    for field_name, labels in {
        "bank_name": ["Bank Name", "State Bank of India", "Bank"],
        "hindi_bank_name": ["भारतीय स्टेट बैंक"],
        "branch_name": ["Branch"],
        "phone": ["Phone No.", "Phone"],
        "account_holder": ["Name"],
        "father_name": ["S/D/H/o", "Father Name", "S/O"],
        "account_type": ["A/c Type", "Account Type"],
        "mop": ["MOP"],
        "address": ["Address"],
    }.items():
        value = extract_labeled_line_value(extracted_text, labels)
        mapped_fields[field_name] = value or mapped_fields.get(field_name, "")

    opened = extract_labeled_line_value(extracted_text, ["A/c Opening Dt", "Account Opening Date"])
    mapped_fields["account_opened"] = normalize_slash_date(opened) or mapped_fields.get("account_opened", "")

    issue_date = extract_labeled_line_value(extracted_text, ["Date of Issue"])
    mapped_fields["date_of_issue"] = normalize_slash_date(issue_date) or mapped_fields.get("date_of_issue", "")

    if "continuation" in mapped_fields and fuzzy_regex.search(r"\bCONTINUATION\b", extracted_text, flags=fuzzy_regex.IGNORECASE):
        mapped_fields["continuation"] = "CONTINUATION"

    if "branch_manager_stamp_present" in mapped_fields:
        mapped_fields["branch_manager_stamp_present"] = bool(fuzzy_regex.search(r"Branch Manager|शाखा प्रबंधक", extracted_text, flags=fuzzy_regex.IGNORECASE))

    return mapped_fields


def enhance_invoice_fields(extracted_text, mapped_fields):
    lines = get_clean_lines(extracted_text)
    text = "\n".join(lines)

    company = ""
    for line in lines[:8]:
        if fuzzy_regex.search(r"MR\.?\s*D\.?I\.?Y|SDN\s+BHD|INVOICE|CASH SALES", line, flags=fuzzy_regex.IGNORECASE):
            company = line
            break

    mapped_fields["company"] = company or mapped_fields.get("company", "")
    mapped_fields["date"] = extract_regex_value(text, r"\b(\d{2}[-/]\d{2}[-/]\d{2,4})\b", flags=0) or mapped_fields.get("date", "")
    mapped_fields["receipt_number"] = extract_labeled_line_value(text, ["Receipt No.", "Invoice No.", "Doc No.", "Slip No."]) or mapped_fields.get("receipt_number", "")

    address_lines = [
        line
        for line in lines
        if fuzzy_regex.search(r"\b(?:LOT|JALAN|TAMAN|NO\.|KAWASAN|SELANGOR|KEMBANGAN)\b", line, flags=fuzzy_regex.IGNORECASE)
    ]
    mapped_fields["address"] = clean_extracted_value(" ".join(address_lines)) or mapped_fields.get("address", "")

    subtotal = extract_labeled_line_value(text, ["Subtotal", "Sub-total", "Total Sales"])
    mapped_fields["subtotal"] = extract_regex_value(subtotal, r"(\d+\.\d{2})", flags=0) or mapped_fields.get("subtotal", "")

    tax = extract_labeled_line_value(text, ["GST", "Tax", "Total Tax"])
    mapped_fields["tax"] = extract_regex_value(tax, r"(\d+\.\d{2})", flags=0) or mapped_fields.get("tax", "")

    discount = extract_labeled_line_value(text, ["Discount", "Disc"])
    mapped_fields["discount"] = extract_regex_value(discount, r"(\d+\.\d{2})", flags=0) or mapped_fields.get("discount", "")

    total = extract_labeled_line_value(text, ["Grand Total", "Total Sales", "Total", "CASH", "Amount"])
    mapped_fields["total"] = extract_regex_value(total, r"(\d+\.\d{2})", flags=0) or mapped_fields.get("total", "")

    if "currency" in mapped_fields and fuzzy_regex.search(r"\b(?:RM|MYR)\b", text, flags=fuzzy_regex.IGNORECASE):
        mapped_fields["currency"] = "RM"

    return mapped_fields


@lru_cache(maxsize=256)
def make_spacing_flexible_label_pattern(label_text):
    # This helps match labels even if PDF/OCR text changes spacing or separators.
    # Example: Employee Name, Employee   Name, Employee-Name, and Employee\nName can all match.
    label_words = label_text.split()
    escaped_words = [fuzzy_regex.escape(word) for word in label_words]

    separator_pattern = r"[\s:：|._-]+"

    return separator_pattern.join(escaped_words)


@lru_cache(maxsize=256)
def get_allowed_fuzzy_errors(label_text):
    # Fuzzy matching helps when OCR reads a label with a tiny mistake.
    # Short labels stay strict so they do not match unrelated text.
    label_length = len(label_text.replace(" ", ""))

    if label_length <= 4:
        return 0

    if label_length <= 12:
        return 1

    return 2


@lru_cache(maxsize=256)
def add_fuzzy_matching_to_pattern(label_pattern, label_text):
    allowed_errors = get_allowed_fuzzy_errors(label_text)

    if allowed_errors == 0:
        return label_pattern

    # This lets the full label have a few OCR mistakes.
    # Example: "Moblle Number" can still match "Mobile Number".
    return f"({label_pattern}){{e<={allowed_errors}}}"


def remove_duplicate_label_matches(label_matches):
    # Avoid duplicate matches when one label is inside another label.
    # Example: "Name" can appear inside "Father Name".
    final_matches = []
    last_end = -1

    for match in label_matches:
        if match["start"] >= last_end:
            final_matches.append(match)
            last_end = match["end"]

    return final_matches


def find_schema_label_positions(extracted_text, schema):
    # Find where each schema label appears in the extracted text.
    # Once we know label positions, we can take the value after each label.
    label_matches = []

    for field_name, label_or_labels in schema.items():
        possible_labels = get_labels_for_field(label_or_labels)

        for label in possible_labels:
            label_text = remove_colon_from_label(label)

            if label_text == "":
                continue

            label_pattern = make_spacing_flexible_label_pattern(label_text)
            label_pattern = add_fuzzy_matching_to_pattern(label_pattern, label_text)
            # The separator after a label is optional.
            # This handles text like "Employee Name Rahul" or "Employee Name: Rahul".
            # A label should not start in the middle of another value.
            # This stops fuzzy matching from taking the last digit of a date as part of the next label.
            pattern = r"(?<![\p{L}\p{N}])" + label_pattern + r"\s*[:：|._-]?\s*"

            for match in fuzzy_regex.finditer(pattern, extracted_text, flags=fuzzy_regex.IGNORECASE):
                label_matches.append({
                    "field_name": field_name,
                    "label": label,
                    "start": match.start(),
                    "end": match.end(),
                })

    label_matches = sorted(
        label_matches,
        key=lambda item: (item["start"], -(item["end"] - item["start"])),
    )

    return remove_duplicate_label_matches(label_matches)


def find_form_end_marker_positions(extracted_text):
    # These words are not fields.
    # They help us stop the last value before it captures signature text.
    end_marker_labels = ["Signature", "Applicant Signature", "Employee Signature"]
    end_markers = []

    for label in end_marker_labels:
        label_pattern = make_spacing_flexible_label_pattern(label)
        label_pattern = add_fuzzy_matching_to_pattern(label_pattern, label)
        pattern = r"(?<![\p{L}\p{N}])" + label_pattern + r"\s*[:：|._-]?\s*"

        for match in fuzzy_regex.finditer(pattern, extracted_text, flags=fuzzy_regex.IGNORECASE):
            end_markers.append({
                "field_name": None,
                "label": label,
                "start": match.start(),
                "end": match.end(),
            })

    return end_markers


def extract_field_values_using_schema(extracted_text, schema):
    # Main idea: a value starts after its label and ends before the next label.
    mapped_fields = {field_name: "" for field_name in schema}
    # Start with empty values so missing fields are easy to see.
    label_matches = find_schema_label_positions(extracted_text, schema)

    # Add end markers so the last field does not capture signature text.
    label_matches = sorted(
        label_matches + find_form_end_marker_positions(extracted_text),
        key=lambda item: item["start"],
    )

    for index, match in enumerate(label_matches):
        field_name = match["field_name"]

        if field_name is None:
            continue

        value_start = match["end"]

        # Value ends where the next label or end marker starts.
        if index + 1 < len(label_matches):
            value_end = label_matches[index + 1]["start"]
        else:
            value_end = len(extracted_text)

        value = extracted_text[value_start:value_end]
        # Clean the value before saving it.
        mapped_fields[field_name] = clean_extracted_value(value)

    if "aadhaar_number" in mapped_fields:
        mapped_fields = enhance_aadhaar_fields(extracted_text, mapped_fields)

    if "pan_number" in mapped_fields:
        mapped_fields = enhance_pan_fields(extracted_text, mapped_fields)

    if "bank_name" in mapped_fields and "account_number" in mapped_fields:
        mapped_fields = enhance_passbook_fields(extracted_text, mapped_fields)

    if "company" in mapped_fields and "total" in mapped_fields:
        mapped_fields = enhance_invoice_fields(extracted_text, mapped_fields)

    return mapped_fields
