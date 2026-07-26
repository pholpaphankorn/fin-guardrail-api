from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv

from app.services.validator import evaluate_thai_id_risk, evaluate_medical_claim_risk
from app.services.extractor import extract_thai_id, extract_medical_receipt
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


@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}


@app.post("/api/v1/validate/thai-id", response_model=RiskAssessmentResponse)
async def validate_thai_id_endpoint(file: UploadFile = File(...)):
    """Validates Thai ID Cards for onboarding & KYC compliance."""
    _validate_image_format(file)

    extracted_data = await extract_thai_id(file)
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

    extracted_data = await extract_medical_receipt(file)
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
