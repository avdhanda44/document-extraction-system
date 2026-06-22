from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import os

import easyocr
from pdf2image import convert_from_path


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
os.environ.setdefault("DOCTR_CACHE_DIR", str(PROJECT_FOLDER / ".doctr-cache"))

# EasyOCR takes time to start.
# I keep it as None first, then create it once only when OCR is really needed.
easyocr_reader = None
paddle_ocr = {}
rapidocr_reader = None
doctr_predictor = None
tesseract_available = False
tesseract_languages = None

IMAGE_PREPROCESSING_MODES = [
    "none",
    "grayscale",
    "threshold",
    "adaptive_threshold",
    "denoise",
    "sharpen",
]


def get_easyocr_reader():
    global easyocr_reader

    if easyocr_reader is None:
        # gpu=False means this will run on a normal CPU.
        easyocr_reader = easyocr.Reader(["en", "hi"], gpu=False)

    return easyocr_reader


def get_paddle_ocr(language="en"):
    global paddle_ocr

    if language not in paddle_ocr:
        try:
            from paddleocr import PaddleOCR
        except ImportError as error:
            raise RuntimeError("PaddleOCR is not installed. Install paddleocr first.") from error

        paddle_ocr[language] = PaddleOCR(use_angle_cls=False, lang=language)

    return paddle_ocr[language]


def get_rapidocr_reader():
    global rapidocr_reader

    if rapidocr_reader is None:
        try:
            from rapidocr import RapidOCR
        except ImportError as error:
            raise RuntimeError("RapidOCR is not installed. Install rapidocr first.") from error

        rapidocr_reader = RapidOCR()

    return rapidocr_reader


def get_doctr_predictor():
    global doctr_predictor

    if doctr_predictor is None:
        try:
            from doctr.models import ocr_predictor
        except ImportError as error:
            raise RuntimeError("docTR is not installed. Install python-doctr[torch] first.") from error

        doctr_predictor = ocr_predictor(pretrained=True)

    return doctr_predictor


def check_tesseract_available():
    global tesseract_available

    if tesseract_available:
        return True

    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        tesseract_available = True
        return True
    except Exception:
        return False


def get_tesseract_languages():
    global tesseract_languages

    if tesseract_languages is not None:
        return tesseract_languages

    try:
        import pytesseract

        tesseract_languages = set(pytesseract.get_languages(config=""))
    except Exception:
        tesseract_languages = set()

    return tesseract_languages


def get_tesseract_language_config():
    languages = get_tesseract_languages()

    if "eng" in languages and "hin" in languages:
        return "eng+hin"

    if "hin" in languages:
        return "hin"

    return "eng"


def get_available_ocr_models():
    # These are the OCR engines this processor knows how to run.
    models = ["easyocr"]

    if check_tesseract_available():
        models.append("tesseract")

    if importlib.util.find_spec("paddleocr") and importlib.util.find_spec("paddle"):
        models.append("paddleocr")

    if importlib.util.find_spec("rapidocr") and importlib.util.find_spec("onnxruntime"):
        models.append("rapidocr")

    if importlib.util.find_spec("doctr") and importlib.util.find_spec("torch"):
        models.append("doctr")

    return models


def read_image_for_processing(image_path):
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is not installed. Install opencv-python first.") from error

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(f"Could not read image file: {image_path}")

    return image


def preprocess_image(image_path, mode="none"):
    # Return an OpenCV image after applying one preprocessing mode.
    # This keeps all image cleanup in this processor instead of spreading it around.
    if mode not in IMAGE_PREPROCESSING_MODES:
        raise ValueError(f"Unknown image preprocessing mode: {mode}")

    import cv2

    image = read_image_for_processing(image_path)

    if mode == "none":
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if mode == "grayscale":
        return gray

    if mode == "threshold":
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    if mode == "adaptive_threshold":
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

    if mode == "denoise":
        return cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)

    if mode == "sharpen":
        blurred = cv2.GaussianBlur(gray, (0, 0), 3)
        return cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)

    return image


def save_processed_image_to_temp_file(image_path, mode, temporary_folder):
    import cv2

    processed_image = preprocess_image(image_path, mode)
    output_path = Path(temporary_folder) / f"{Path(image_path).stem}_{mode}.png"
    cv2.imwrite(str(output_path), processed_image)
    return output_path


def get_ocr_image_path(image_path, preprocessing_mode, temporary_folder):
    if preprocessing_mode == "none":
        return image_path

    return save_processed_image_to_temp_file(image_path, preprocessing_mode, temporary_folder)


def extract_text_from_image_easyocr(image_path, preprocessing_mode="none"):
    # Use OCR for image files like PNG and JPG.
    reader = get_easyocr_reader()

    with TemporaryDirectory() as temporary_folder:
        ocr_image_path = get_ocr_image_path(image_path, preprocessing_mode, temporary_folder)
        detected_text = reader.readtext(str(ocr_image_path))

    # EasyOCR gives extra details for each match, but item[1] is the text we need.
    return "\n".join(item[1] for item in detected_text).strip()


def extract_text_from_image_tesseract(image_path, preprocessing_mode="threshold"):
    # Extract text using Tesseract OCR.
    if not check_tesseract_available():
        raise RuntimeError("Tesseract OCR is not installed. Please install it first.")

    try:
        import pytesseract

        processed_image = preprocess_image(image_path, preprocessing_mode)
        text = pytesseract.image_to_string(processed_image, lang=get_tesseract_language_config())
        return text.strip()
    except Exception as error:
        raise RuntimeError(f"Tesseract OCR failed: {error}") from error


def extract_text_from_image_paddleocr(image_path, preprocessing_mode="none"):
    # Extract text using PaddleOCR.
    text_lines = []
    errors = []

    with TemporaryDirectory() as temporary_folder:
        ocr_image_path = get_ocr_image_path(image_path, preprocessing_mode, temporary_folder)

        for language in ["en", "hi"]:
            try:
                paddle = get_paddle_ocr(language)
                results = paddle.ocr(str(ocr_image_path))
                text_lines.extend(extract_text_lines_from_paddle_results(results))
            except Exception as error:
                errors.append(f"{language}: {error}")

    final_text = "\n".join(dict.fromkeys(text_lines)).strip()

    if final_text:
        return final_text

    raise RuntimeError(f"PaddleOCR failed: {'; '.join(errors)}")


def extract_text_from_image_rapidocr(image_path, preprocessing_mode="none"):
    # RapidOCR uses compact ONNX models and runs efficiently on CPU.
    reader = get_rapidocr_reader()

    with TemporaryDirectory() as temporary_folder:
        ocr_image_path = get_ocr_image_path(image_path, preprocessing_mode, temporary_folder)
        result = reader(str(ocr_image_path))

    text_lines = [str(text).strip() for text in (result.txts or ()) if str(text).strip()]
    return "\n".join(text_lines)


def extract_text_from_image_doctr(image_path, preprocessing_mode="none"):
    # docTR combines document text detection and recognition using PyTorch.
    try:
        from doctr.io import DocumentFile
    except ImportError as error:
        raise RuntimeError("docTR is not installed. Install python-doctr[torch] first.") from error

    predictor = get_doctr_predictor()

    with TemporaryDirectory() as temporary_folder:
        ocr_image_path = get_ocr_image_path(image_path, preprocessing_mode, temporary_folder)
        document = DocumentFile.from_images(str(ocr_image_path))
        result = predictor(document)

    return result.render().strip()


def extract_text_lines_from_paddle_results(results):
    text_lines = []

    def add_text(value):
        text = str(value).strip()
        if text:
            text_lines.append(text)

    def walk(value):
        if value is None:
            return

        if isinstance(value, dict):
            for key in ["rec_texts", "texts", "text"]:
                if key not in value:
                    continue

                item = value[key]
                if isinstance(item, list):
                    for text in item:
                        add_text(text)
                else:
                    add_text(item)

            for item in value.values():
                walk(item)
            return

        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and isinstance(value[1], (list, tuple)) and value[1]:
                first_item = value[1][0]
                if isinstance(first_item, str):
                    add_text(first_item)

            for item in value:
                walk(item)
            return

    walk(results)

    return list(dict.fromkeys(text_lines))


def extract_text_from_image(image_path, model_name="easyocr", preprocessing_mode="none"):
    # Default image OCR entry point used by text_extractor.py.
    if model_name == "easyocr":
        return extract_text_from_image_easyocr(image_path, preprocessing_mode)

    if model_name == "tesseract":
        return extract_text_from_image_tesseract(image_path, preprocessing_mode)

    if model_name == "paddleocr":
        return extract_text_from_image_paddleocr(image_path, preprocessing_mode)

    if model_name == "rapidocr":
        return extract_text_from_image_rapidocr(image_path, preprocessing_mode)

    if model_name == "doctr":
        return extract_text_from_image_doctr(image_path, preprocessing_mode)

    raise ValueError(f"Unknown OCR model: {model_name}")


def extract_text_from_image_with_all_models(image_path, preprocessing_mode="none"):
    # Run every OCR model and keep errors per model instead of stopping the whole job.
    results = {}

    for model_name in get_available_ocr_models():
        try:
            results[model_name] = {
                "text": extract_text_from_image(image_path, model_name, preprocessing_mode),
                "error": "",
            }
        except Exception as error:
            results[model_name] = {
                "text": "",
                "error": str(error),
            }

    return results


def extract_text_from_scanned_pdf(pdf_path, model_name="easyocr", preprocessing_mode="none"):
    # Scanned PDFs are basically images inside a PDF.
    # So first we convert each page into an image, then run OCR on those images.
    try:
        pages = convert_from_path(str(pdf_path), dpi=350)
    except Exception as error:
        raise RuntimeError("Scanned PDF files need Poppler installed.") from error

    text_from_pages = []

    with TemporaryDirectory() as temporary_folder:
        temporary_folder = Path(temporary_folder)

        for page_number, page in enumerate(pages, start=1):
            image_path = temporary_folder / f"page_{page_number}.png"
            page.save(image_path, "PNG")
            text_from_pages.append(extract_text_from_image(image_path, model_name, preprocessing_mode))

    final_text = "\n".join(text_from_pages).strip()

    if final_text == "":
        raise ValueError("No readable text found in scanned PDF.")

    return final_text
