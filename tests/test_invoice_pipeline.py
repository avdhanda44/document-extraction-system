import unittest
from pathlib import Path
from unittest.mock import patch

from Backend.json_generator import get_sheet_rows_and_headers
from main import (
    compare_with_ground_truth,
    extract_invoice_fields_from_text,
    process_document_pdf_folder,
)


class InvoiceComparisonTests(unittest.TestCase):
    def test_source_image_metadata_is_not_scored(self):
        ground_truth = {
            "company": "SOON HUAT MACHINERY ENTERPRISE",
            "date": "11/01/2019",
            "address": "NO.53 JALAN PUTRA 1",
            "total": "327.00",
            "source_image": "invoice.jpg",
        }

        comparison = compare_with_ground_truth(dict(ground_truth), ground_truth)

        self.assertEqual(comparison["total_fields"], 4)
        self.assertEqual(comparison["accuracy_percent"], 100)
        self.assertFalse(
            comparison["field_results"]["source_image"]["used_for_accuracy"]
        )

    def test_invoice_parser_extracts_receipt_fields(self):
        text = """
        SOON HUAT MACHINERY ENTERPRISE
        NO.53 JALAN PUTRA 1, TAMAN SRI PUTRA, 81200 JOHOR BAHRU
        CASH SALES
        Doc No. : CS00004040   Date: 11/01/2019
        SUB-TOTAL 327.00
        TOTAL TAX 0.00
        DISCOUNT 0.00
        TOTAL SALES RM 327.00
        """

        document_type, fields = extract_invoice_fields_from_text(text, "invoice.jpg")

        self.assertEqual(document_type, "invoice")
        self.assertEqual(fields["receipt_number"], "CS00004040")
        self.assertEqual(fields["total"], "327.00")
        self.assertEqual(fields["currency"], "MYR")


class InvoiceReportTests(unittest.TestCase):
    def test_invoice_report_has_focused_sheets(self):
        models = ["easyocr", "tesseract"]
        easyocr_fields = {
            "company": {
                "used_for_accuracy": True,
                "match": True,
                "similarity_percent": 92,
            },
            "date": {
                "used_for_accuracy": True,
                "match": False,
                "similarity_percent": 0,
            },
            "source_image": {"used_for_accuracy": False, "match": False},
        }
        tesseract_fields = {
            **easyocr_fields,
            "date": {
                "used_for_accuracy": True,
                "match": True,
                "similarity_percent": 100,
            },
        }
        rows = [{
            "image address": "invoice.jpg",
            "easyocr": 50,
            "tesseract": 100,
            "easyocr processing time (seconds)": 2.0,
            "tesseract processing time (seconds)": 1.0,
            "__field_results": {
                "easyocr": easyocr_fields,
                "tesseract": tesseract_fields,
            },
            "__model_failed": {"easyocr": False, "tesseract": False},
            "__model_complete": {"easyocr": False, "tesseract": True},
        }]

        sheets = get_sheet_rows_and_headers(rows, models, "invoice")

        self.assertEqual(
            [sheet["name"] for sheet in sheets],
            ["accuracy", "field_accuracy", "summary"],
        )
        self.assertEqual(
            {row["field"] for row in sheets[1]["rows"]},
            {"company", "date"},
        )
        self.assertEqual(
            sheets[2]["rows"][1]["complete record rate (%)"],
            100,
        )


class ScannedPdfOutputTests(unittest.TestCase):
    @patch("main.save_accuracy_excel")
    @patch("main.list_document_pdfs", return_value=[])
    @patch("main.get_available_ocr_models", return_value=["tesseract"])
    def test_scanned_pdf_report_uses_scanned_output_folder(
        self,
        _get_models,
        _list_pdfs,
        save_accuracy_excel,
    ):
        save_accuracy_excel.return_value = Path("report.xlsx")

        process_document_pdf_folder(
            "aadhaar",
            Path("dataset/generated_docs/aadhaar/pdf/scanned"),
            Path("dataset/ground_truth/aadhaar/pdf/scanned"),
            object(),
            "aadhaar_pdf_model_accuracy.xlsx",
        )

        self.assertEqual(
            save_accuracy_excel.call_args.kwargs["output_format"],
            "pdf/scanned",
        )


if __name__ == "__main__":
    unittest.main()
