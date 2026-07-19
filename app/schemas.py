from pydantic import BaseModel, Field
from typing import List, Optional

# --- Onboarding / KYC Models ---
class ThaiIDExtraction(BaseModel):
    id_number: str = Field(description="The 13-digit Thai National ID number")
    first_name_en: str = Field(description="First name in English")
    last_name_en: str = Field(description="Last name in English")
    date_of_birth: str = Field(description="Date of birth in YYYY-MM-DD format")
    expiry_date: str = Field(description="Expiry date in YYYY-MM-DD format or 'Lifetime'")

# --- Claims Models ---
class LineItem(BaseModel):
    description: str = Field(description="Itemized description of the medical service or medicine")
    cost: float = Field(description="Cost of this individual item")

class MedicalReceiptExtraction(BaseModel):
    hospital_name: str = Field(description="Name of the hospital or medical clinic")
    receipt_date: str = Field(description="Date the receipt was issued in YYYY-MM-DD format")
    items: List[LineItem] = Field(description="List of all itemized charges on the receipt")
    total_amount: float = Field(description="The total balance stated on the receipt")

# --- Final System Response Model ---
class RiskAssessmentResponse(BaseModel):
    document_type: str = Field(description="'thai_id' or 'medical_receipt'")
    status: str = Field(description="APPROVED, FLAGGED_FOR_REVIEW, or REJECTED")
    extracted_data: dict = Field(description="The raw data extracted by the Vision LLM")
    validation_flags: List[str] = Field(description="List of issues caught by deterministic code rule checks")
    risk_score: float = Field(description="Calculated risk level between 0.0 (Safe) and 1.0 (Critical)")
    reasoning: str = Field(description="Detailed text explaining the verdict status")