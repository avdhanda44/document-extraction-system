# --------------------------------------------------------------------------------
# # Save Output
# 
# This notebook saves the extracted dictionary as a JSON file in the outputs folder.
# --------------------------------------------------------------------------------

import json
from datetime import datetime

# Save JSON output
# A timestamp is added to the file name so each run creates a new output instead of replacing an older one.
def save_json(file_path, extracted_json):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_output_path = outputs_folder / f"{file_path.stem}_{timestamp}.json"

    with open(json_output_path, "w", encoding="utf-8") as file:
        json.dump(extracted_json, file, indent=4, ensure_ascii=False)

    return json_output_path

