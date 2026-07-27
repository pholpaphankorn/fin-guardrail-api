from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv

from app.services.validator import evaluate_thai_id_risk, evaluate_medical_claim_risk
from app.services.extractor import extract_thai_id, extract_medical_receipt
from app.services.image_processor import evaluate_image_blur
from app.schemas import RiskAssessmentResponse

load_dotenv()

app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0",
)


def _validate_image_format(file: UploadFile):
    """Helper to validate file extension prior to processing."""
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Upload an image file (.png, .jpg, .jpeg).",
        )


def _calculate_status_and_reasoning(risk_score: float) -> tuple[str, str]:
    """Applies risk threshold routing rules."""
    if risk_score >= 0.7:
        return (
            "REJECTED",
            "System safety guardrails blocked transaction processing due to high systemic compliance risk.",
        )
    elif risk_score > 0.0:
        return (
            "FLAGGED_FOR_REVIEW",
            "Document contains validation alerts. Routed automatically to administrative review desks.",
        )
    return (
        "APPROVED",
        "Document passed all structural parameters and mathematical balancing audits cleanly.",
    )


def _build_unreadable_document_response(doc_type: str, flag_reason: str) -> dict:
    """Returns a standard HTTP 200 rejection response when pre-processing or extraction fails."""
    return {
        "document_type": doc_type,
        "status": "REJECTED",
        "extracted_data": {},
        "validation_flags": [flag_reason],
        "risk_score": 1.0,
        "reasoning": "Document quality failed pre-processing or legibility guardrails.",
    }


@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}


@app.post("/api/v1/validate/thai-id", response_model=RiskAssessmentResponse)
async def validate_thai_id_endpoint(file: UploadFile = File(...)):
    """Validates Thai ID Cards for onboarding & KYC compliance."""
    _validate_image_format(file)

    # Read image bytes for quality assessment
    file_bytes = await file.read()
    
    # 1. Pre-processing Blur Guardrail Check
    is_blurry, blur_score = evaluate_image_blur(file_bytes)
    if is_blurry:
        return _build_unreadable_document_response(
            "thai_id",
            f"BLURRY_IMAGE_DETECTED: Focus score ({blur_score:.1f}) fell below safety threshold (100.0). Please re-take a clear photo."
        )

    # Reset file pointer or pass bytes to extractor
    file.file.seek(0)
    extracted_data = await extract_thai_id(file)

    if extracted_data is None:
        return _build_unreadable_document_response(
            "thai_id",
            "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries."
        )

    flags, risk_score = evaluate_thai_id_risk(extracted_data)
    status, reasoning = _calculate_status_and_reasoning(risk_score)

    return {
        "document_type": "thai_id",
        "status": status,
        "extracted_data": extracted_data.model_dump(),
        "validation_flags": flags,
        "risk_score": risk_score,
        "reasoning": reasoning,
    }


@app.post("/api/v1/validate/medical-receipt", response_model=RiskAssessmentResponse)
async def validate_medical_receipt_endpoint(file: UploadFile = File(...)):
    """Validates Medical Receipts for insurance claims processing."""
    _validate_image_format(file)

    file_bytes = await file.read()

    # 1. Pre-processing Blur Guardrail Check
    is_blurry, blur_score = evaluate_image_blur(file_bytes)
    if is_blurry:
        return _build_unreadable_document_response(
            "medical_receipt",
            f"BLURRY_IMAGE_DETECTED: Focus score ({blur_score:.1f}) fell below safety threshold (100.0). Please re-take a clear photo."
        )

    file.file.seek(0)
    extracted_data = await extract_medical_receipt(file)

    if extracted_data is None:
        return _build_unreadable_document_response(
            "medical_receipt",
            "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries."
        )

    flags, risk_score = evaluate_medical_claim_risk(extracted_data)
    status, reasoning = _calculate_status_and_reasoning(risk_score)

    return {
        "document_type": "medical_receipt",
        "status": status,
        "extracted_data": extracted_data.model_dump(),
        "validation_flags": flags,
        "risk_score": risk_score,
        "reasoning": reasoning,
    }