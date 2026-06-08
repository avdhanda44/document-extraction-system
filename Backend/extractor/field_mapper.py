import regex as fuzzy_regex


def get_labels_for_field(label_or_labels):
    # Some fields have one label.
    # Some fields have many labels, like English + Hindi labels for Aadhaar.
    if isinstance(label_or_labels, list):
        return label_or_labels

    return [label_or_labels]


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


def make_spacing_flexible_label_pattern(label_text):
    # This helps match labels even if PDF/OCR text changes spacing or separators.
    # Example: Employee Name, Employee   Name, Employee-Name, and Employee\nName can all match.
    label_words = label_text.split()
    escaped_words = [fuzzy_regex.escape(word) for word in label_words]

    separator_pattern = r"[\s:：|._-]+"

    return separator_pattern.join(escaped_words)


def get_allowed_fuzzy_errors(label_text):
    # Fuzzy matching helps when OCR reads a label with a tiny mistake.
    # Short labels stay strict so they do not match unrelated text.
    label_length = len(label_text.replace(" ", ""))

    if label_length <= 4:
        return 0

    if label_length <= 12:
        return 1

    return 2


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

    return mapped_fields
