import json
import os
import base64
from fastapi import UploadFile, HTTPException
from ollama import Client  # Import the programmatic Client constructor
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from dotenv import load_dotenv

# Ensure system environments are actively loaded prior to client creation
load_dotenv()
# Instantiate the client pointing to Ollama's managed cloud environment
# It uses the key from your environment variable for authentication
ollama_client = Client(
    host="https://ollama.com",
    headers={'Authorization': f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
)


def encode_file_to_base64(file_bytes: bytes) -> str:
    """Encodes raw file bytes into a base64 string for the Vision API."""
    return base64.b64encode(file_bytes).decode('utf-8')


async def extract_document_data(file: UploadFile, doc_type: str):
    """
    Reads an uploaded file and dispatches it to an Ollama Cloud Vision model
    enforcing a strict JSON response schema matching our Pydantic definitions.
    """
    # 1. Check if Mock Mode is globally active
    USE_MOCK = os.environ.get("USE_MOCK_LLM", "false").lower() == "true"
    
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read file stream: {str(e)}")

    if not file_bytes:
        raise HTTPException(
            status_code=400, detail="The uploaded file is empty.")

    base64_image = encode_file_to_base64(file_bytes)

    # 1. Map target validation schemas and specialized processing prompts
    if doc_type == "thai_id":
        target_schema = ThaiIDExtraction
        prompt_instruction = (
            "Analyze the image of the Thai National ID Card and extract the fields into JSON. "
            "You MUST use these exact keys in the root of the JSON object: "
            "'id_number' (the 13 digit string), 'first_name_en', 'last_name_en', "
            "'date_of_birth' (YYYY-MM-DD), and 'expiry_date' (YYYY-MM-DD).\n"
            "Do not nest fields inside objects like 'name' or 'english'."
        )
        mock_file_path = "data/mock_jsons/mock_thai_id.json"
    elif doc_type == "medical_receipt":
        target_schema = MedicalReceiptExtraction
        prompt_instruction = (
            "Analyze the image of the medical receipt or clinic invoice and extract the details into JSON.\n\n"
            "You MUST structure the JSON with these exact keys at the root:\n"
            "- 'hospital_name': The clear text string name of the clinic or hospital.\n"
            "- 'receipt_date': The date of service or issue formatted strictly as YYYY-MM-DD.\n"
            "- 'items': An array/list of individual medical services or medications. Each object in this list MUST contain exactly two keys: 'description' (string) and 'cost' (number/float).\n"
            "- 'total_amount': The absolute total balance stated on the invoice as a single number/float.\n\n"
            "Do not invent outer objects or nest the root fields. Extract numbers as clean floats without currency symbols (e.g., use 500.0 instead of '500 THB')."
        )
        mock_file_path = "data/mock_jsons/mock_medical_receipt.json"
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported document mapping.")

    if USE_MOCK:
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            # Instantly validate raw dictionary records into full Pydantic models
            return target_schema.model_validate(raw_json)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Local mock reading failure: {str(e)}")

    # 2. Query Ollama's Cloud cluster using structural formatting options
    try:
        response = ollama_client.chat(
            model="gemma4:31b-cloud",  # Frontier cloud-hosted multimodal model
            messages=[
                {
                    "requirement": "user",
                    "content": prompt_instruction,
                    "images": [base64_image]
                }
            ],
            # Pass structural parameters to constrain output generation to valid schema objects
            format=target_schema.model_json_schema(),
            options={"temperature": 0.0}
        )

        # 3. Deserialize back into a strictly safe, validated Pydantic type instance
        raw_content = cleanup_raw_content(response.message.content)
        extracted_object = target_schema.model_validate_json(raw_content)

        return extracted_object

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ollama Cloud Engine execution failure: {str(e)}")


def cleanup_raw_content(raw_content: str) -> str:
    """
    Cleans up the raw string output from the Ollama model to ensure it is valid JSON.
    This is a temporary measure until the model's output is fully reliable.
    """
    raw_content = raw_content.strip()

    # FIX: Clean out markdown code fences if the model wraps them
    if raw_content.startswith("```"):
        # Remove opening fence like ```json or ```
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        else:
            raw_content = raw_content[3:]

        # Remove closing fence
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]

        raw_content = raw_content.strip()
    return raw_content
