import json
import base64
import logging
import asyncio
import time
from typing import Optional
from fastapi import HTTPException
from pydantic import ValidationError
from ollama import Client
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from app.config import Settings, get_settings
from app.observability import metrics

logger = logging.getLogger(__name__)

THAI_ID_PROMPT_VERSION = "thai-id-extraction-v1.0.0"
MEDICAL_RECEIPT_PROMPT_VERSION = "medical-receipt-extraction-v1.0.0"
PROMPT_VERSIONS = {
    "thai_id": THAI_ID_PROMPT_VERSION,
    "medical_receipt": MEDICAL_RECEIPT_PROMPT_VERSION,
}


def _create_ollama_client(settings: Settings) -> Client:
    """Build a provider client from the validated settings for this request."""
    api_key = (
        settings.ollama_api_key.get_secret_value()
        if settings.ollama_api_key is not None
        else ""
    )
    return Client(
        host=settings.ollama_host,
        headers={"Authorization": f"Bearer {api_key}"},
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
    file_bytes: bytes, prompt_instruction: str, target_schema, mock_file_path: str
):
    """
    Core private handler for processing pre-processed image bytes, managing mock mode,
    and querying Ollama. Includes an automatic single-retry loop with a correction prompt.
    Returns None if extraction completely fails after retries.
    """
    settings = get_settings()

    if not file_bytes:
        raise HTTPException(
            status_code=400, detail="The provided image byte stream is empty."
        )

    if settings.use_mock_llm:
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            return target_schema.model_validate(raw_json)
        except (OSError, json.JSONDecodeError, ValidationError):
            logger.error("Mock extraction response is unavailable or schema-invalid.")
            raise HTTPException(
                status_code=500,
                detail="Local mock response is unavailable or invalid.",
            )

    if not settings.live_provider_ready:
        raise HTTPException(
            status_code=503,
            detail="Vision provider is not configured. Set OLLAMA_API_KEY or enable mock mode.",
        )

    client = _create_ollama_client(settings)
    base64_image = encode_file_to_base64(file_bytes)

    async def call_provider(prompt: str, attempt: int):
        started = time.perf_counter()
        if attempt > 1:
            metrics.increment("model_retries_total")
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat,
                    model=settings.vision_model,
                    messages=[
                        {
                            "requirement": "user",
                            "content": prompt,
                            "images": [base64_image],
                        }
                    ],
                    format=target_schema.model_json_schema(),
                    options={"temperature": 0.0},
                ),
                timeout=settings.vision_timeout_seconds,
            )
            metrics.observe_model((time.perf_counter() - started) * 1000, "responses")
            return response
        except TimeoutError as exc:
            metrics.observe_model((time.perf_counter() - started) * 1000, "timeouts")
            raise HTTPException(
                status_code=504, detail="Vision provider request timed out."
            ) from exc
        except Exception:
            metrics.observe_model((time.perf_counter() - started) * 1000, "errors")
            raise

    # --- ATTEMPT 1 ---
    try:
        response = await call_provider(prompt_instruction, attempt=1)

        raw_content = cleanup_raw_content(response.message.content)
        return target_schema.model_validate_json(raw_content)

    except HTTPException:
        raise
    except (ValidationError, json.JSONDecodeError, ValueError):
        metrics.increment("model_schema_failures_total")
        logger.warning(
            "Vision output failed schema validation on attempt 1; retrying once."
        )

        # --- ATTEMPT 2 (Correction Retry) ---
        correction_prompt = (
            f"{prompt_instruction}\n\n"
            "CRITICAL ERROR: Your previous response failed JSON schema validation.\n\n"
            "Re-analyze the image and output ONLY valid JSON matching the exact required keys."
        )

        try:
            retry_response = await call_provider(correction_prompt, attempt=2)

            raw_retry_content = cleanup_raw_content(retry_response.message.content)
            return target_schema.model_validate_json(raw_retry_content)

        except HTTPException:
            raise
        except (ValidationError, json.JSONDecodeError, ValueError):
            metrics.increment("model_schema_failures_total")
            logger.error(
                "Vision output failed schema validation after the bounded retry."
            )
            return None

        except Exception as exc:
            logger.error("Vision provider retry failed.")
            raise HTTPException(
                status_code=502,
                detail="Vision provider retry failed.",
            ) from exc

    except Exception as exc:
        logger.error("Vision provider request failed.")
        raise HTTPException(
            status_code=502, detail="Vision provider request failed."
        ) from exc


# --- Public Functional Extractors ---


async def extract_thai_id(file_bytes: bytes) -> Optional[ThaiIDExtraction]:
    """Extracts Thai National ID card fields into structured JSON from image bytes."""
    prompt = (
        f"PROMPT_VERSION: {THAI_ID_PROMPT_VERSION}\n\n"
        "Analyze the image of the Thai National ID Card and extract the fields into JSON.\n\n"
        "### REQUIRED JSON STRUCTURE\n"
        "1. 'visual_checks': An object performing structural verification with exact boolean keys:\n"
        "   - 'has_card_title': true if header 'บัตรประจำตัวประชาชน' or 'Thai National ID Card' is visible.\n"
        "   - 'has_garuda_emblem': true if official Garuda emblem on top-left is visible.\n"
        "   - 'has_microchip': true if metallic smart chip on middle-left is visible.\n"
        "   - 'has_portrait_photo': true if holder's photo on bottom-right side is visible.\n"
        "   - 'has_barcode': true if vertical barcode on left margin is visible.\n"
        "   For each check, return 'value' (boolean), 'confidence' (0.0 to 1.0), and 'reasoning' (brief note).\n\n"
        "2. Dynamic Text Fields at Root Level:\n"
        "   - 'id_number': 13-digit Thai ID number string.\n"
        "   - 'first_name_th', 'last_name_th': Name in Thai.\n"
        "   - 'first_name_en', 'last_name_en': Name in English.\n"
        "   - 'date_of_birth': Formatted strictly as YYYY-MM-DD.\n"
        "   - 'address_th': Full address in Thai.\n"
        "   - 'issue_date': Date of issue formatted strictly as YYYY-MM-DD.\n"
        "   - 'expiry_date': Date of expiry formatted strictly as YYYY-MM-DD or 'Lifetime'.\n"
        "   - 'issuing_officer_th': Issuing officer name/title under the official stamp.\n"
        "   - 'religion_th': Stated religion in Thai (e.g., 'พุทธ', 'คริสต์', 'อิสลาม'). Set value to null if omitted/not listed.\n\n"
        "### FIELD OBJECT FORMAT\n"
        "For EVERY field above, you MUST return an object containing:\n"
        "1. 'value': The extracted value (boolean for visual_checks, string for text fields). Set to null if completely unreadable or missing.\n"
        "2. 'confidence': A float between 0.0 and 1.0 indicating clarity and legibility:\n"
        "   - 0.9-1.0: Crystal clear, crisp text/feature with zero ambiguity.\n"
        "   - 0.7-0.89: Slightly faint, small font, or light glare, but legible.\n"
        "   - 0.1-0.69: Severely blurry, partially cut off, obscured, or uncertain.\n"
        "   - 0.0-0.09: Text or visual feature is completely missing/illegible.\n"
        "3. 'reasoning': A brief 1-sentence note explaining why confidence is below 1.0."
    )
    return await _call_vision_model(
        file_bytes=file_bytes,
        prompt_instruction=prompt,
        target_schema=ThaiIDExtraction,
        mock_file_path="data/mock_jsons/mock_thai_id.json",
    )


async def extract_medical_receipt(
    file_bytes: bytes,
) -> Optional[MedicalReceiptExtraction]:
    """Extracts medical receipt line items and balance totals into structured JSON from image bytes."""
    prompt = (
        f"PROMPT_VERSION: {MEDICAL_RECEIPT_PROMPT_VERSION}\n\n"
        "Analyze the image of the medical receipt or clinic invoice and extract the details into JSON.\n\n"
        "You MUST structure the JSON with these exact keys at the root:\n"
        "- 'hospital_name': The clear text string name of the clinic or hospital.\n"
        "- 'receipt_date': The date of service or issue formatted strictly as YYYY-MM-DD.\n"
        "- 'items': An array/list of individual medical services or medications. Each object in this list MUST contain exactly two keys: 'description' (string) and 'cost' (number/float).\n"
        "- 'total_amount': The absolute total balance stated on the invoice as a single number/float.\n"
        "For EACH field, you MUST return an object containing:\n"
        "1. 'value': The extracted string value (e.g., '1234567890121' for id_number, or 'YYYY-MM-DD' / 'Lifetime' for expiry_date). Set to null if completely missing or unreadable.\n"
        "2. 'confidence': A float between 0.0 and 1.0 indicating legibility and clarity:\n"
        "   - 0.9-1.0: Crystal clear, crisp text with zero ambiguity.\n"
        "   - 0.7-0.89: Slightly faint, small font, or light glare, but legible.\n"
        "   - 0.1-0.69: Severely blurry, partially cropped, obstructed, or uncertain reading.\n"
        "   - 0.0-0.09: Text is completely illegible or missing from document.\n"
        "3. 'reasoning': A brief 1-sentence note explaining why confidence is below 1.0 (e.g., 'Slight glare over expiration date', 'Crisp text')."
        "Do not invent outer objects or nest the root fields. Extract numbers as clean floats without currency symbols (e.g., use 500.0 instead of '500 THB')."
    )
    return await _call_vision_model(
        file_bytes=file_bytes,
        prompt_instruction=prompt,
        target_schema=MedicalReceiptExtraction,
        mock_file_path="data/mock_jsons/mock_medical_receipt.json",
    )
