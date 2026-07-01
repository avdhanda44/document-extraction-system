def create_final_json_output(document_result, classification, mapped_fields, validation):
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
