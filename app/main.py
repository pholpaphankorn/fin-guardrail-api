from app.services.validator import evaluate_thai_id_risk, evaluate_medical_claim_risk
from app.services.extractor import extract_document_data
from app.schemas import RiskAssessmentResponse
from enum import Enum

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from dotenv import load_dotenv

load_dotenv()


# 1. Define your choices using an Enum
class DocumentType(str, Enum):
    THAI_ID = "thai_id"
    MEDICAL_RECEIPT = "medical_receipt"


app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}


@app.post("/api/v1/validate-document", response_model=RiskAssessmentResponse)
async def validate_document(
    file: UploadFile = File(...),
    doc_type: DocumentType = Query(
        ..., description="Choose 'thai_id' or 'medical_receipt'"
    ),
):
    if doc_type not in ["thai_id", "medical_receipt"]:
        raise HTTPException(status_code=400, detail="Invalid doc_type parameter.")

    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400, detail="Invalid file format. Upload an image file."
        )

    # 1. Trigger the Visual Extractor layer
    extracted_pydantic_data = await extract_document_data(file, doc_type)
    raw_dict_data = extracted_pydantic_data.model_dump()

    # 2. Route processing straight through our deterministic rule validators
    if doc_type == "thai_id":
        flags, risk_score = evaluate_thai_id_risk(extracted_pydantic_data)
    else:
        flags, risk_score = evaluate_medical_claim_risk(extracted_pydantic_data)

    # 3. Apply operational routing thresholds matching security parameters
    if risk_score >= 0.7:
        status = "REJECTED"
        reasoning = "System safety guardrails blocked transaction processing due to high systemic compliance risk."
    elif risk_score > 0.0:
        status = "FLAGGED_FOR_REVIEW"
        reasoning = "Document contains validation alerts. Routed automatically to administrative review desks."
    else:
        status = "APPROVED"
        reasoning = "Document passed all structural parameters and mathematical balancing audits cleanly."

    return {
        "document_type": doc_type,
        "status": status,
        "extracted_data": raw_dict_data,
        "validation_flags": flags,
        "risk_score": risk_score,
        "reasoning": reasoning,
    }
