from .processors.image_processor import get_available_ocr_models


digital_pdf_extractors = ["pypdf", "pymupdf", "pdfminer", "pdfplumber"]
scanned_pdf_ocr_models = ["doctr", "paddleocr", "easyocr"]
image_ocr_models = ["doctr", "tesseract", "paddleocr", "easyocr"]

document_engine_preferences = {
    "aadhaar_full": ["paddleocr", "easyocr", "doctr"],
    "aadhaar_front": ["paddleocr", "easyocr", "doctr"],
    "aadhaar_back": ["paddleocr", "easyocr", "doctr"],
    "pan_card": ["tesseract", "doctr", "paddleocr", "easyocr"],
    "passbook": ["doctr", "paddleocr", "easyocr"],
    "invoice": ["doctr", "paddleocr", "easyocr"],
}


def get_available_models_in_policy_order(policy_models):
    available_models = set(get_available_ocr_models())
    return [model_name for model_name in policy_models if model_name in available_models]


def get_image_ocr_policy():
    return get_available_models_in_policy_order(image_ocr_models)


def get_scanned_pdf_ocr_policy():
    return get_available_models_in_policy_order(scanned_pdf_ocr_models)


def get_document_engine_preference(document_type, engine):
    preferred_engines = document_engine_preferences.get(document_type, [])

    if engine not in preferred_engines:
        return 0

    return len(preferred_engines) - preferred_engines.index(engine)
