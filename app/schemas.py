from pydantic import BaseModel, Field
from typing import List, Optional


# --- Onboarding / KYC Models ---
class ThaiIDExtraction(BaseModel):
    # Required field (actively validated by rule checks)
    id_number: str = Field(description="The 13-digit Thai National ID number")

    # Optional fields (extracted if visible, but won't crash parsing if missing)
    first_name_en: Optional[str] = Field(
        default=None, description="First name in English"
    )
    last_name_en: Optional[str] = Field(
        default=None, description="Last name in English"
    )
    date_of_birth: Optional[str] = Field(
        default=None, description="Date of birth in YYYY-MM-DD format"
    )

    # Required field (actively validated for expiry risk)
    expiry_date: str = Field(
        description="Expiry date in YYYY-MM-DD format or 'Lifetime'"
    )

    # Model confidence assessment
    confidence_score: float = Field(
        default=1.0,
        description="Confidence score between 0.0 (Uncertain/Blurry) and 1.0 (Certain/Clear) regarding document legibility and extraction accuracy."
    )


# --- Claims Models ---
class LineItem(BaseModel):
    description: str = Field(
        description="Itemized description of the medical service or medicine"
    )
    cost: float = Field(description="Cost of this individual item")


class MedicalReceiptExtraction(BaseModel):
    # Optional field (informational, not strictly validated in financial balance)
    hospital_name: Optional[str] = Field(
        default=None, description="Name of the hospital or medical clinic"
    )

    # Optional date field
    receipt_date: Optional[str] = Field(
        default=None, description="Date the receipt was issued in YYYY-MM-DD format"
    )

    # Required fields (used directly in arithmetic math validation)
    items: List[LineItem] = Field(
        description="List of all itemized charges on the receipt"
    )
    total_amount: float = Field(description="The total balance stated on the receipt")

    # Model confidence assessment
    confidence_score: float = Field(
        default=1.0,
        description="Confidence score between 0.0 (Uncertain/Blurry) and 1.0 (Certain/Clear) regarding document legibility and extraction accuracy."
    )


# --- Final System Response Model ---
class RiskAssessmentResponse(BaseModel):
    document_type: str = Field(description="'thai_id' or 'medical_receipt'")
    status: str = Field(description="APPROVED, FLAGGED_FOR_REVIEW, or REJECTED")
    extracted_data: dict = Field(description="The raw data extracted by the Vision LLM")
    validation_flags: List[str] = Field(
        description="List of issues caught by deterministic code rule checks"
    )
    risk_score: float = Field(
        description="Calculated risk level between 0.0 (Safe) and 1.0 (Critical)"
    )
    reasoning: str = Field(description="Detailed text explaining the verdict status")