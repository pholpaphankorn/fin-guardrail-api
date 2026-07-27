from fastapi import FastAPI, Depends
from dotenv import load_dotenv

from app.services.validator import (
    evaluate_thai_id_risk,
    evaluate_medical_claim_risk,
    calculate_status_and_reasoning,
    build_unreadable_document_response,
)
from app.services.extractor import extract_thai_id, extract_medical_receipt
from app.services.image_processor import evaluate_blur_dependency
from app.schemas import RiskAssessmentResponse

load_dotenv()

app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}


@app.post("/api/v1/validate/thai-id", response_model=RiskAssessmentResponse)
async def validate_thai_id_endpoint(
    image_data: tuple[bytes, bool, float] = Depends(evaluate_blur_dependency),
):
    """Validates Thai ID Cards for onboarding & KYC compliance."""
    processed_bytes, is_blurry, blur_score = image_data

    # 1. Pre-processing Blur Guardrail Check (HTTP 200 Business Rejection)
    if is_blurry:
        return build_unreadable_document_response(
            "thai_id",
            f"BLURRY_IMAGE_DETECTED: Focus score ({blur_score:.1f}) fell below safety threshold (100.0). Please re-take a clear photo.",
        )

    # 2. Extract Data via Vision LLM using the resized bytes
    extracted_data = await extract_thai_id(processed_bytes)

    if extracted_data is None:
        return build_unreadable_document_response(
            "thai_id",
            "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries.",
        )

    # 3. Evaluate Risk Rules
    flags, risk_score = evaluate_thai_id_risk(extracted_data)
    status, reasoning = calculate_status_and_reasoning(risk_score)

    return {
        "document_type": "thai_id",
        "status": status,
        "extracted_data": extracted_data.model_dump(),
        "validation_flags": flags,
        "risk_score": risk_score,
        "reasoning": reasoning,
    }


@app.post("/api/v1/validate/medical-receipt", response_model=RiskAssessmentResponse)
async def validate_medical_receipt_endpoint(
    image_data: tuple[bytes, bool, float] = Depends(evaluate_blur_dependency),
):
    """Validates Medical Receipts for insurance claims processing."""
    processed_bytes, is_blurry, blur_score = image_data

    # 1. Pre-processing Blur Guardrail Check (HTTP 200 Business Rejection)
    if is_blurry:
        return build_unreadable_document_response(
            "medical_receipt",
            f"BLURRY_IMAGE_DETECTED: Focus score ({blur_score:.1f}) fell below safety threshold (100.0). Please re-take a clear photo.",
        )

    # 2. Extract Data via Vision LLM using the resized bytes
    extracted_data = await extract_medical_receipt(processed_bytes)

    if extracted_data is None:
        return build_unreadable_document_response(
            "medical_receipt",
            "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries.",
        )

    # 3. Evaluate Risk Rules
    flags, risk_score = evaluate_medical_claim_risk(extracted_data)
    status, reasoning = calculate_status_and_reasoning(risk_score)

    return {
        "document_type": "medical_receipt",
        "status": status,
        "extracted_data": extracted_data.model_dump(),
        "validation_flags": flags,
        "risk_score": risk_score,
        "reasoning": reasoning,
    }
