import io
import unittest
from pathlib import Path
from unittest.mock import patch

import main
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


class CliTests(unittest.TestCase):
    def test_process_command_uses_single_file_pipeline(self):
        with patch("main.process_uploaded_document") as process_document:
            process_document.return_value = {"output_path": Path("outputs/result.json")}
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                main.main(["process", "RahulVerma.pdf"])

        process_document.assert_called_once_with("RahulVerma.pdf")
        self.assertIn("Done. File processed", output.getvalue())

    def test_legacy_single_file_mode_still_works(self):
        with patch("main.process_uploaded_document") as process_document:
            process_document.return_value = {"output_path": Path("outputs/result.json")}
            with patch("sys.stdout", new_callable=io.StringIO):
                main.main(["RahulVerma.pdf"])

        process_document.assert_called_once_with("RahulVerma.pdf")

    def test_new_image_batch_command_routes_to_document_batch(self):
        with patch("main.process_pan_folder") as process_batch:
            process_batch.return_value = {
                "processed_images": 2,
                "excel_output": Path("outputs/pan/image/report.xlsx"),
            }
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                main.main(["batch", "pan", "--format", "image"])

        process_batch.assert_called_once_with()
        self.assertIn("Processed 2 PAN images", output.getvalue())

    def test_new_digital_pdf_batch_rejects_invoice_until_supported(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main.main(["batch", "invoice", "--format", "pdf", "--pdf-type", "digital"])


if __name__ == "__main__":
    unittest.main()
