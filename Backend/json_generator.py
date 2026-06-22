import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def find_outputs_folder_for_json_files():
    # VS Code may run the file from Backend or from the project folder.
    # This keeps JSON files saved in the project-level outputs folder.
    current_folder = Path.cwd()

    if (current_folder / "outputs").exists():
        return current_folder / "outputs"

    if (current_folder.parent / "outputs").exists():
        return current_folder.parent / "outputs"

    return current_folder / "outputs"


outputs_folder = find_outputs_folder_for_json_files()
outputs_folder.mkdir(exist_ok=True)


def get_document_outputs_folder(document_name, file_format=None):
    output_folder = outputs_folder / document_name

    if file_format:
        output_folder = output_folder / file_format

    output_folder.mkdir(parents=True, exist_ok=True)
    return output_folder


def create_final_json_output(document_result, classification, mapped_fields, validation):
    # This creates the final JSON in the format we want to save.
    # First we keep extracted output, then we keep validation details.
    return {
        "extracted_output": {
            "file_name": document_result["file_path"].name,
            "file_type": document_result["file_type"],
            "document_type": classification["document_type"],
            "confidence_percent": classification["confidence_percent"],
            "confidence_level": classification["confidence_level"],
            "fields": validation["extracted_data"],
        },
        "validation": {
            "summary": validation["validation_summary"],
            "field_results": validation["validation_results"],
        },
    }


def save_final_json_file(final_json):
    # Save one output file per uploaded document.
    # If we run the same file again, this will replace the old output for that file.
    file_stem = Path(final_json["extracted_output"]["file_name"]).stem
    document_name = final_json["extracted_output"]["document_type"]
    file_type = final_json["extracted_output"]["file_type"]
    file_format = "image" if file_type in {"png", "jpg", "jpeg"} else file_type
    output_folder = get_document_outputs_folder(document_name, file_format)
    output_path = output_folder / f"{file_stem}_output.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_json, json_file, indent=4, ensure_ascii=False)

    return output_path


def save_aadhaar_json_file(image_path, final_json):
    return save_document_json_file(image_path, final_json, "aadhaar", "image")


def save_document_json_file(source_path, final_json, document_name, file_format="image"):
    output_folder = get_document_outputs_folder(document_name, file_format)
    output_path = output_folder / f"{Path(source_path).stem}_{document_name}_output.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_json, json_file, indent=4, ensure_ascii=False)

    return output_path


def excel_column_name(column_number):
    name = ""

    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(65 + remainder) + name

    return name


def make_shared_strings(values):
    shared_strings = []
    shared_string_indexes = {}

    for value in values:
        text = str(value)
        if text not in shared_string_indexes:
            shared_string_indexes[text] = len(shared_strings)
            shared_strings.append(text)

    return shared_strings, shared_string_indexes


def make_sheet_xml(headers, rows, shared_string_indexes):
    sheet_rows = []
    all_rows = [headers] + [[row.get(header, "") for header in headers] for row in rows]

    for row_index, row_values in enumerate(all_rows, start=1):
        cells = []

        for column_index, value in enumerate(row_values, start=1):
            cell_reference = f"{excel_column_name(column_index)}{row_index}"

            if isinstance(value, (int, float)):
                cells.append(f'<c r="{cell_reference}"><v>{value}</v></c>')
            else:
                shared_index = shared_string_indexes[str(value)]
                cells.append(f'<c r="{cell_reference}" t="s"><v>{shared_index}</v></c>')

        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )


def collect_sheet_string_values(headers, rows):
    values = list(headers)

    for row in rows:
        for header in headers:
            value = row.get(header, "")

            if not isinstance(value, (int, float)):
                values.append(value)

    return values


def get_sheet_rows_and_headers(rows, model_names):
    time_headers = [f"{model_name} processing time (seconds)" for model_name in model_names]
    headers = (
        ["image address", "document side", "image quality category"]
        + list(model_names)
        + time_headers
    )
    front_rows = [row for row in rows if row.get("document side") == "front"]
    back_rows = [row for row in rows if row.get("document side") == "back"]
    summary_rows = make_accuracy_summary_rows(rows, model_names)
    summary_headers = ["group", "value", "image count"] + list(model_names) + time_headers
    quality_headers = (
        ["image quality category", "image count"]
        + list(model_names)
        + time_headers
        + [
            "best model",
            "best accuracy",
            "worst model",
            "worst accuracy",
            "accuracy difference",
            "fastest model",
            "fastest average time (seconds)",
            "slowest model",
            "slowest average time (seconds)",
        ]
    )

    return [
        {
            "name": "accuracy",
            "headers": headers,
            "rows": rows,
        },
        {
            "name": "quality_front",
            "headers": quality_headers,
            "rows": make_quality_summary_rows(front_rows, model_names),
        },
        {
            "name": "quality_back",
            "headers": quality_headers,
            "rows": make_quality_summary_rows(back_rows, model_names),
        },
        {
            "name": "summary",
            "headers": summary_headers,
            "rows": summary_rows,
        },
    ]


def average_model_scores(rows, model_names):
    averages = {}

    for model_name in model_names:
        scores = [
            row.get(model_name, 0)
            for row in rows
            if isinstance(row.get(model_name, 0), (int, float))
        ]
        averages[model_name] = round(sum(scores) / len(scores), 2) if scores else 0

    return averages


def average_model_processing_times(rows, model_names):
    averages = {}

    for model_name in model_names:
        header = f"{model_name} processing time (seconds)"
        times = [
            row.get(header)
            for row in rows
            if isinstance(row.get(header), (int, float))
        ]
        averages[header] = round(sum(times) / len(times), 4) if times else 0

    return averages


def make_quality_summary_rows(rows, model_names):
    quality_rows = []
    quality_values = sorted({
        row.get("image quality category", "unknown") or "unknown"
        for row in rows
    })

    for quality in quality_values:
        matching_rows = [
            row for row in rows
            if (row.get("image quality category", "unknown") or "unknown") == quality
        ]
        averages = average_model_scores(matching_rows, model_names)
        average_times = average_model_processing_times(matching_rows, model_names)
        ranked_models = sorted(
            averages.items(),
            key=lambda item: (-item[1], item[0]),
        )
        ranked_times = sorted(
            (
                (model_name, average_times[f"{model_name} processing time (seconds)"])
                for model_name in model_names
            ),
            key=lambda item: (item[1], item[0]),
        )
        best_model, best_accuracy = ranked_models[0] if ranked_models else ("", 0)
        worst_model, worst_accuracy = ranked_models[-1] if ranked_models else ("", 0)
        fastest_model, fastest_time = ranked_times[0] if ranked_times else ("", 0)
        slowest_model, slowest_time = ranked_times[-1] if ranked_times else ("", 0)

        quality_rows.append({
            "image quality category": quality,
            "image count": len(matching_rows),
            **averages,
            **average_times,
            "best model": best_model,
            "best accuracy": best_accuracy,
            "worst model": worst_model,
            "worst accuracy": worst_accuracy,
            "accuracy difference": round(best_accuracy - worst_accuracy, 2),
            "fastest model": fastest_model,
            "fastest average time (seconds)": fastest_time,
            "slowest model": slowest_model,
            "slowest average time (seconds)": slowest_time,
        })

    return quality_rows


def make_accuracy_summary_rows(rows, model_names):
    grouped_rows = []

    for group_name in ["document side", "image quality category"]:
        values = sorted({row.get(group_name, "unknown") or "unknown" for row in rows})

        for value in values:
            matching_rows = [row for row in rows if (row.get(group_name, "unknown") or "unknown") == value]
            summary_row = {
                "group": group_name,
                "value": value,
                "image count": len(matching_rows),
            }

            summary_row.update(average_model_scores(matching_rows, model_names))
            summary_row.update(average_model_processing_times(matching_rows, model_names))

            grouped_rows.append(summary_row)

    return grouped_rows


def save_accuracy_excel(
    rows,
    model_names,
    file_name="aadhaar_model_accuracy.xlsx",
    output_subfolder=None,
    output_format=None,
):
    sheets = get_sheet_rows_and_headers(rows, model_names)
    string_values = []

    for sheet in sheets:
        string_values.extend(collect_sheet_string_values(sheet["headers"], sheet["rows"]))

    shared_strings, shared_string_indexes = make_shared_strings(string_values)

    shared_strings_xml = "".join(
        f"<si><t>{escape(value)}</t></si>" for value in shared_strings
    )
    output_folder = (
        get_document_outputs_folder(output_subfolder, output_format)
        if output_subfolder
        else outputs_folder
    )
    output_path = output_folder / file_name
    content_type_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index, _sheet in enumerate(sheets, start=1)
    )
    workbook_sheets_xml = "".join(
        f'<sheet name="{escape(sheet["name"])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    workbook_relationships_xml = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index, _sheet in enumerate(sheets, start=1)
    )
    shared_strings_relationship_id = f"rId{len(sheets) + 1}"

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f"{content_type_overrides}"
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '</Types>',
        )
        xlsx.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        xlsx.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets_xml}</sheets>"
            '</workbook>',
        )
        xlsx.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_relationships_xml}"
            f'<Relationship Id="{shared_strings_relationship_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            '</Relationships>',
        )

        for index, sheet in enumerate(sheets, start=1):
            sheet_xml = make_sheet_xml(sheet["headers"], sheet["rows"], shared_string_indexes)
            xlsx.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml)

        xlsx.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
            f"{shared_strings_xml}</sst>",
        )

    return output_path
