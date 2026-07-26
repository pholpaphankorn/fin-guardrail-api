import json
import os
import base64
from fastapi import UploadFile, HTTPException
from ollama import Client
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from dotenv import load_dotenv

load_dotenv()

ollama_client = Client(
    host="https://ollama.com",
    headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"},
)


def encode_file_to_base64(file_bytes: bytes) -> str:
    """Encodes raw file bytes into a base64 string for the Vision API."""
    return base64.b64encode(file_bytes).decode("utf-8")


def cleanup_raw_content(raw_content: str) -> str:
    """Cleans up raw markdown code fences from LLM responses."""
    raw_content = raw_content.strip()
    if raw_content.startswith("```"):
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        else:
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        raw_content = raw_content.strip()
    return raw_content


async def _call_vision_model(
    file: UploadFile, prompt_instruction: str, target_schema, mock_file_path: str
):
    """Core private handler for reading files, managing mock mode, and querying Ollama."""
    USE_MOCK = os.environ.get("USE_MOCK_LLM", "false").lower() == "true"

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read file stream: {str(e)}"
        )

    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if USE_MOCK:
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            return target_schema.model_validate(raw_json)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Local mock reading failure: {str(e)}"
            )

    base64_image = encode_file_to_base64(file_bytes)

    try:
        response = ollama_client.chat(
            model="gemma4:31b-cloud",
            messages=[
                {
                    "requirement": "user",
                    "content": prompt_instruction,
                    "images": [base64_image],
                }
            ],
            format=target_schema.model_json_schema(),
            options={"temperature": 0.0},
        )

        raw_content = cleanup_raw_content(response.message.content)
        return target_schema.model_validate_json(raw_content)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ollama Cloud Engine execution failure: {str(e)}"
        )


# --- Public Functional Extractors ---


async def extract_thai_id(file: UploadFile) -> ThaiIDExtraction:
    """Extracts Thai National ID card fields into structured JSON."""
    prompt = (
        "Analyze the image of the Thai National ID Card and extract the fields into JSON. "
        "You MUST use these exact keys in the root of the JSON object: "
        "'id_number' (the 13 digit string), 'first_name_en', 'last_name_en', "
        "'date_of_birth' (YYYY-MM-DD), and 'expiry_date' (YYYY-MM-DD).\n"
        "Do not nest fields inside objects like 'name' or 'english'."
    )
    return await _call_vision_model(
        file=file,
        prompt_instruction=prompt,
        target_schema=ThaiIDExtraction,
        mock_file_path="data/mock_jsons/mock_thai_id.json",
    )


async def extract_medical_receipt(file: UploadFile) -> MedicalReceiptExtraction:
    """Extracts medical receipt line items and balance totals into structured JSON."""
    prompt = (
        "Analyze the image of the medical receipt or clinic invoice and extract the details into JSON.\n\n"
        "You MUST structure the JSON with these exact keys at the root:\n"
        "- 'hospital_name': The clear text string name of the clinic or hospital.\n"
        "- 'receipt_date': The date of service or issue formatted strictly as YYYY-MM-DD.\n"
        "- 'items': An array/list of individual medical services or medications. Each object in this list MUST contain exactly two keys: 'description' (string) and 'cost' (number/float).\n"
        "- 'total_amount': The absolute total balance stated on the invoice as a single number/float.\n\n"
        "Do not invent outer objects or nest the root fields. Extract numbers as clean floats without currency symbols (e.g., use 500.0 instead of '500 THB')."
    )
    return await _call_vision_model(
        file=file,
        prompt_instruction=prompt,
        target_schema=MedicalReceiptExtraction,
        mock_file_path="data/mock_jsons/mock_medical_receipt.json",
    )
