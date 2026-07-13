import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from Backend.extractors.document_classification import (
    aadhaar_full_schema,
    invoice_schema,
    pan_card_schema,
    passbook_schema,
)
from Backend.extractors.validation import validate_extracted_fields


LLM_MODEL_PREFIX = "llm:"
VISION_LLM_MODELS = [
    f"{LLM_MODEL_PREFIX}qwen2.5vl:7b",
    f"{LLM_MODEL_PREFIX}llama3.2-vision:11b",
]
TEXT_LLM_MODELS = [
    f"{LLM_MODEL_PREFIX}qwen2.5:7b-instruct",
    f"{LLM_MODEL_PREFIX}llama3.1:8b",
]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_OPTIONS = {
    "temperature": 0,
    "top_p": 0.2,
}
ollama_model_tags_cache = {
    "loaded": False,
    "models": set(),
    "error": "",
}


DOCUMENT_SCHEMAS = {
    "aadhaar": ("aadhaar_full", aadhaar_full_schema),
    "pan": ("pan_card", pan_card_schema),
    "passbook": ("passbook", passbook_schema),
    "invoice": ("invoice", invoice_schema),
}


def is_llm_model(model_name):
    return str(model_name).startswith(LLM_MODEL_PREFIX)


def get_vision_llm_models():
    return get_configured_llm_models("VISION_LLM_MODELS", VISION_LLM_MODELS)


def get_text_llm_models():
    return get_configured_llm_models("TEXT_LLM_MODELS", TEXT_LLM_MODELS)


def get_configured_llm_models(environment_name, default_models):
    configured_models = os.environ.get(environment_name, "").strip()

    if not configured_models:
        return list(default_models)

    model_names = []
    for model_name in configured_models.split(","):
        model_name = model_name.strip()

        if not model_name:
            continue

        if not is_llm_model(model_name):
            model_name = f"{LLM_MODEL_PREFIX}{model_name}"

        model_names.append(model_name)

    return model_names


def get_ollama_model_name(model_name):
    model_name = str(model_name)

    if model_name.startswith(LLM_MODEL_PREFIX):
        return model_name[len(LLM_MODEL_PREFIX):]

    return model_name


def get_document_schema(document_name):
    if document_name not in DOCUMENT_SCHEMAS:
        raise ValueError(f"Unknown LLM document type: {document_name}")

    return DOCUMENT_SCHEMAS[document_name]


def read_image_as_base64(image_path):
    with Path(image_path).open("rb") as image_file:
        return base64.b64encode(image_file.read()).decode("ascii")


def make_llm_prompt(document_name, source_name, schema, text=None):
    field_names = list(schema)
    text_instruction = (
        "Use only the document text below."
        if text is not None
        else "Use only the attached document image."
    )
    text_block = f"\n\nDOCUMENT TEXT:\n{text}" if text is not None else ""

    return f"""
You extract structured fields from Indian document test data.
Document type: {document_name}
Source file: {source_name}

{text_instruction}
Return one valid JSON object only. Do not include markdown or explanation.
Use exactly these keys:
{json.dumps(field_names, ensure_ascii=False)}

Rules:
- If a field is missing or unreadable, use an empty string.
- Keep dates and numbers as they appear when possible.
- For boolean fields, use true or false.
- For address-like fields, keep useful full text.
{text_block}
""".strip()


def call_ollama_generate(model_name, prompt, image_path=None):
    ensure_ollama_model_available(model_name)

    payload = {
        "model": get_ollama_model_name(model_name),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": OLLAMA_OPTIONS,
    }

    if image_path is not None:
        payload["images"] = [read_image_as_base64(image_path)]

    request = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    response_payload = read_ollama_json_response(request)

    return response_payload.get("response", "")


def read_ollama_json_response(request):
    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {error.code}: {details}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Could not reach Ollama. Start Ollama and pull the configured LLM models first."
        ) from error


def get_ollama_model_tags():
    if ollama_model_tags_cache["loaded"]:
        if ollama_model_tags_cache["error"]:
            raise RuntimeError(ollama_model_tags_cache["error"])

        return ollama_model_tags_cache["models"]

    request = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/tags",
        method="GET",
    )

    try:
        response_payload = read_ollama_json_response(request)
    except RuntimeError as error:
        ollama_model_tags_cache["loaded"] = True
        ollama_model_tags_cache["error"] = str(error)
        raise

    models = response_payload.get("models", [])
    ollama_model_tags_cache["loaded"] = True
    ollama_model_tags_cache["models"] = {
        model.get("name")
        for model in models
        if isinstance(model, dict) and model.get("name")
    }
    return ollama_model_tags_cache["models"]


def ensure_ollama_model_available(model_name):
    ollama_model_name = get_ollama_model_name(model_name)
    available_model_names = get_ollama_model_tags()

    if ollama_model_name in available_model_names:
        return

    raise RuntimeError(
        f"Ollama model '{ollama_model_name}' is not installed. "
        f"Run: ollama pull {ollama_model_name}"
    )


def parse_json_object(raw_response):
    raw_response = str(raw_response or "").strip()

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_response, flags=re.DOTALL)

        if not match:
            raise ValueError("LLM response did not contain a JSON object.")

        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON was not an object.")

    return parsed


def normalize_llm_fields(parsed_fields, schema):
    normalized = {}

    for field_name in schema:
        value = parsed_fields.get(field_name, "")

        if value is None:
            value = ""

        normalized[field_name] = value

    return normalized


def make_llm_classification(document_type, schema):
    return {
        "document_type": document_type,
        "schema": schema,
        "confidence_percent": 100,
        "confidence_level": "High",
    }


def make_llm_result(document_name, source_path, model_name, raw_response):
    document_type, schema = get_document_schema(document_name)
    extracted_fields = normalize_llm_fields(parse_json_object(raw_response), schema)

    if document_name == "invoice" and not extracted_fields.get("source_image"):
        extracted_fields["source_image"] = Path(source_path).name

    classification = make_llm_classification(document_type, schema)
    validation = validate_extracted_fields(classification, extracted_fields)

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
        "raw_text": raw_response,
    }


def process_image_with_llm(document_name, image_path, model_name):
    _document_type, schema = get_document_schema(document_name)
    prompt = make_llm_prompt(document_name, Path(image_path).name, schema)
    raw_response = call_ollama_generate(model_name, prompt, image_path=image_path)
    return make_llm_result(document_name, image_path, model_name, raw_response)


def process_text_with_llm(document_name, text, source_path, model_name):
    _document_type, schema = get_document_schema(document_name)
    prompt = make_llm_prompt(document_name, Path(source_path).name, schema, text=text)
    raw_response = call_ollama_generate(model_name, prompt)
    return make_llm_result(document_name, source_path, model_name, raw_response)
