from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from dotenv import load_dotenv
from app.schemas import RiskAssessmentResponse
from app.services.extractor import extract_document_data

# Ensure system environments are actively loaded prior to client creation
load_dotenv()

app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"status": "healthy", "service": "fin-guardrail-api"}

@app.post("/api/v1/validate-document", response_model=RiskAssessmentResponse)
async def validate_document(
    file: UploadFile = File(...),
    doc_type: str = Query(..., description="Choose 'thai_id' or 'medical_receipt'")
):
    # 1. Basic format verification guardrails
    if doc_type not in ["thai_id", "medical_receipt"]:
        raise HTTPException(status_code=400, detail="Invalid doc_type parameter. Choose 'thai_id' or 'medical_receipt'.")
        
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PNG, JPG, and JPEG images are supported for processing.")

    # 2. Trigger the Multimodal Vision Extractor
    extracted_pydantic_data = await extract_document_data(file, doc_type)
    
    # Converting the structured Pydantic object into a vanilla dictionary for the API payload
    raw_dict_data = extracted_pydantic_data.model_dump()

    # 3. Interim placeholder mapping for Day 2 Guardrails & Scoring
    # (Tomorrow we will replace these constants with automated rule evaluations)
    mock_response = {
        "document_type": doc_type,
        "status": "APPROVED", 
        "extracted_data": raw_dict_data,
        "validation_flags": [],
        "risk_score": 0.05,
        "reasoning": "Data successfully processed through the multimodal schema parser engine."
    }
    
    return mock_response