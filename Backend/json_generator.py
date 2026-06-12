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

if not outputs_folder.exists():
    raise FileNotFoundError("The outputs folder does not exist.")


def get_document_outputs_folder(document_name):
    output_folder = outputs_folder / document_name
    output_folder.mkdir(exist_ok=True)
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
    output_path = outputs_folder / f"{file_stem}_output.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(final_json, json_file, indent=4, ensure_ascii=False)

    return output_path


def save_aadhaar_json_file(image_path, final_json):
    return save_document_json_file(image_path, final_json, "aadhaar")


def save_document_json_file(image_path, final_json, document_name):
    output_path = get_document_outputs_folder(document_name) / f"{Path(image_path).stem}_{document_name}_output.json"

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
    headers = ["image address", "document side", "image quality category"] + list(model_names)
    front_rows = [row for row in rows if row.get("document side") == "front"]
    back_rows = [row for row in rows if row.get("document side") == "back"]
    summary_rows = make_accuracy_summary_rows(rows, model_names)
    summary_headers = ["group", "value", "image count"] + list(model_names)

    return [
        {
            "name": "accuracy",
            "headers": headers,
            "rows": rows,
        },
        {
            "name": "front",
            "headers": headers,
            "rows": front_rows,
        },
        {
            "name": "back",
            "headers": headers,
            "rows": back_rows,
        },
        {
            "name": "summary",
            "headers": summary_headers,
            "rows": summary_rows,
        },
    ]


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

            for model_name in model_names:
                scores = [
                    row.get(model_name, 0)
                    for row in matching_rows
                    if isinstance(row.get(model_name, 0), (int, float))
                ]
                summary_row[model_name] = round(sum(scores) / len(scores), 2) if scores else 0

            grouped_rows.append(summary_row)

    return grouped_rows


def save_accuracy_excel(rows, model_names, file_name="aadhaar_model_accuracy.xlsx", output_subfolder=None):
    sheets = get_sheet_rows_and_headers(rows, model_names)
    string_values = []

    for sheet in sheets:
        string_values.extend(collect_sheet_string_values(sheet["headers"], sheet["rows"]))

    shared_strings, shared_string_indexes = make_shared_strings(string_values)

    shared_strings_xml = "".join(
        f"<si><t>{escape(value)}</t></si>" for value in shared_strings
    )
    output_folder = get_document_outputs_folder(output_subfolder) if output_subfolder else outputs_folder
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
