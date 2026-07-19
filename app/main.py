from fastapi import FastAPI, UploadFile, File, HTTPException
from app.schemas import RiskAssessmentResponse

app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}

@app.post("/api/v1/validate-document", response_model=RiskAssessmentResponse)
async def validate_document(file: UploadFile = File(...)):
    # Validate file type extension
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PNG, JPG, JPEG, and PDF are supported.")
    
    # Placeholder block mimicking a successful pass-through pipeline for Day 1
    # We will hook up app.services.extractor and validator here on Day 2
    mock_response = {
        "document_type": "medical_receipt",
        "status": "APPROVED",
        "extracted_data": {
            "hospital_name": "Mock Bangkok Hospital",
            "receipt_date": "2026-01-01",
            "items": [{"description": "Consultation", "cost": 500.0}],
            "total_amount": 500.0
        },
        "validation_flags": [],
        "risk_score": 0.0,
        "reasoning": "Document signature matches, metadata is pristine, and arithmetic validated successfully."
    }
    
    return mock_response