import io
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import testing.testing as testing_cli
from Backend.api import app
from Backend.pipeline import classify_and_extract_fields


class PipelineTests(unittest.TestCase):
    def test_classify_and_extract_employee_form_text(self):
        text = """
        Employee Name: Test User
        Employee ID: EMP-100
        Date of Birth: 01/02/1990
        Date of Joining: 03/04/2020
        Mobile Number: 9876543210
        Email: test.user@example.com
        """

        classification, mapped_fields, validation = classify_and_extract_fields(text)

        self.assertEqual(classification["document_type"], "employee_form")
        self.assertEqual(mapped_fields["employee_name"], "Test User")
        self.assertTrue(validation["validation_summary"]["ready_to_save"])

    def test_full_aadhaar_extracts_front_and_back_fields_from_mixed_raw_text(self):
        text = """
        भारत सरकार
        GOVERNMENT OF INDIA
        आरव मेहता
        Aarav Mehta
        जन्म तिथि / DOB : 1991-03-18
        पुरुष / Male
        SAMPLE PHOTO
        0601 3665 5668
        आधार - आम आदमी का अधिकार
        भारतीय विशिष्ट पहचान प्राधिकरण
        UNIQUE IDENTIFICATION AUTHORITY OF INDIA
        पता: S/O: Suresh Mehta
        पुत्र: सुरेश मेहता 14, Lotus Park Road
        14, लोटस पार्क रोड Pune, Maharashtra
        पुणे, महाराष्ट्र 411001
        411001
        0601 3665 5668
        P.O. Box No. 1947,
        1947
        help@uidai.gov.in www.uidai.gov.in
        Bengaluru-560 001
        1800 180 1947
        """

        classification, mapped_fields, validation = classify_and_extract_fields(text)

        self.assertEqual(classification["document_type"], "aadhaar_full")
        self.assertEqual(mapped_fields["aadhaar_number"], "0601 3665 5668")
        self.assertEqual(mapped_fields["name"], "Aarav Mehta")
        self.assertEqual(mapped_fields["hindi_name"], "आरव मेहता")
        self.assertEqual(mapped_fields["date_of_birth"], "1991-03-18")
        self.assertEqual(mapped_fields["gender"], "Male")
        self.assertEqual(mapped_fields["pincode"], "411001")
        self.assertIn("Lotus Park Road", mapped_fields["address"])
        self.assertIn("Pune", mapped_fields["address"])
        self.assertNotIn("लोटस", mapped_fields["address"])
        self.assertEqual(mapped_fields["relationship_label"], "Suresh Mehta")
        self.assertEqual(mapped_fields["hindi_relationship_label"], "सुरेश मेहता")
        self.assertEqual(mapped_fields["hindi_address"], "14, लोटस पार्क रोड पुणे, महाराष्ट्र 411001")
        self.assertIn("hindi_address_lines", mapped_fields)
        self.assertEqual(validation["validation_summary"]["invalid_fields"], 0)

    def test_pan_extracts_fields_from_clean_front_raw_text(self):
        text = """
        INCOME TAX DEPARTMENT
        GOVT. OF INDIA
        Permanent Account Number
        KLMPC9364T
        Name
        RAHUL CHATTERJEE
        Father's Name
        15112021
        SUBHASH CHATTERJEE
        Date of Birth
        / Signature
        06/12/1988
        राहुल चटर्जी
        सुभाष चटर्जी
        """

        classification, mapped_fields, validation = classify_and_extract_fields(text)

        self.assertEqual(classification["document_type"], "pan_card")
        self.assertEqual(mapped_fields["pan_number"], "KLMPC9364T")
        self.assertEqual(mapped_fields["name"], "Rahul Chatterjee")
        self.assertEqual(mapped_fields["father_name"], "Subhash Chatterjee")
        self.assertEqual(mapped_fields["date_of_birth"], "1988-12-06")
        self.assertEqual(mapped_fields["hindi_name"], "राहुल चटर्जी")
        self.assertEqual(mapped_fields["hindi_father_name"], "सुभाष चटर्जी")
        self.assertTrue(mapped_fields["signature_present"])
        self.assertEqual(mapped_fields["card_issue_date_text"], "15112021")
        self.assertEqual(validation["validation_summary"]["invalid_fields"], 0)

    def test_passbook_extracts_sample_layout_fields(self):
        text = """
        State Bank of India
        भारतीय स्टेट बैंक
        Branch: Chennai Main
        Branch Code: 61255
        Email: sbin.0004567@bank.co.in
        Phone No. 07489165
        MICR 568513756
        IFSC SBIN0004567
        Name: Mr. Kabir Iyer
        S/O: Suresh Iyer
        CIF Number 096581461
        Account No. 31026166816901
        A/c Type REGULAR SAVINGS BANK ACCOUNT
        Address 17B Lake View Road Chennai Tamil Nadu 600041
        MOP SINGLE
        A/c Opening Dt 22/12/2011
        Nom Reg No 00000652848
        Customer's PAN KABPI2212M
        Date of Issue 22/12/2011
        CONTINUATION
        Branch Manager
        """

        classification, mapped_fields, validation = classify_and_extract_fields(text)

        self.assertEqual(classification["document_type"], "passbook")
        self.assertEqual(mapped_fields["ifsc"], "SBIN0004567")
        self.assertEqual(mapped_fields["account_number"], "31026166816901")
        self.assertEqual(mapped_fields["pan_number"], "KABPI2212M")
        self.assertEqual(mapped_fields["account_opened"], "22/12/2011")
        self.assertTrue(mapped_fields["branch_manager_stamp_present"])
        self.assertEqual(validation["validation_summary"]["invalid_fields"], 0)

    def test_invoice_extracts_sample_layout_fields(self):
        text = """
        MR. D.I.Y. (M) SDN BHD
        TAX INVOICE
        LOT 1851-A & 1851-B, JALAN KPB 6,
        KAWASAN PERINDUSTRIAN BALAKONG,
        43300 SERI KEMBANGAN, SELANGOR
        Date 25-03-18
        Receipt No. X51005757324
        Total Sales RM 50.80
        CASH 50.80
        """

        classification, mapped_fields, validation = classify_and_extract_fields(text)

        self.assertEqual(classification["document_type"], "invoice")
        self.assertIn("MR. D.I.Y", mapped_fields["company"])
        self.assertEqual(mapped_fields["date"], "25-03-18")
        self.assertIn("JALAN KPB", mapped_fields["address"])
        self.assertEqual(mapped_fields["total"], "50.80")
        self.assertEqual(mapped_fields["receipt_number"], "X51005757324")
        self.assertEqual(validation["validation_summary"]["invalid_fields"], 0)


class CliTests(unittest.TestCase):
    def test_process_command_uses_single_file_pipeline(self):
        with patch("testing.testing.process_uploaded_document") as process_document:
            process_document.return_value = {"output_path": Path("outputs/result.json")}
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                testing_cli.main(["process", "RahulVerma.pdf"])

        process_document.assert_called_once_with("RahulVerma.pdf")
        self.assertIn("Done. File processed", output.getvalue())

    def test_legacy_single_file_mode_still_works(self):
        with patch("testing.testing.process_uploaded_document") as process_document:
            process_document.return_value = {"output_path": Path("outputs/result.json")}
            with patch("sys.stdout", new_callable=io.StringIO):
                testing_cli.main(["RahulVerma.pdf"])

        process_document.assert_called_once_with("RahulVerma.pdf")

    def test_new_image_batch_command_routes_to_document_batch(self):
        with patch("testing.testing.process_pan_folder") as process_batch:
            process_batch.return_value = {
                "processed_images": 2,
                "excel_output": Path("outputs/pan/image/report.xlsx"),
            }
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                testing_cli.main(["batch", "pan", "--format", "image"])

        process_batch.assert_called_once_with()
        self.assertIn("Processed 2 PAN images", output.getvalue())

    def test_new_digital_pdf_batch_rejects_invoice_until_supported(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                testing_cli.main(["batch", "invoice", "--format", "pdf", "--pdf-type", "digital"])


class ApiTests(unittest.TestCase):
    def test_extract_endpoint_previews_without_saving_output(self):
        result = {
            "final_json": {
                "extracted_output": {
                    "file_name": "sample.png",
                    "file_type": "png",
                    "document_type": "unknown",
                    "confidence_percent": 0,
                    "confidence_level": "low",
                    "fields": {},
                },
                "validation": {
                    "summary": {
                        "total_fields_checked": 0,
                        "valid_fields": 0,
                        "invalid_fields": 0,
                        "fields_with_warnings": 0,
                    },
                    "field_results": {},
                },
            },
            "document_result": {
                "final_text": "",
                "extraction_engine": "test",
                "extraction_method": "mock",
            },
            "output_path": None,
        }

        with patch("Backend.api.process_uploaded_document", return_value=result) as process_document:
            client = TestClient(app)
            response = client.post(
                "/api/extract",
                files={"file": ("sample.png", b"\x89PNG\r\n\x1a\n", "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        process_document.assert_called_once()
        self.assertFalse(process_document.call_args.kwargs["save_output"])
        self.assertEqual(response.json()["output_path"], "")


if __name__ == "__main__":
    unittest.main()
