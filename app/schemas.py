from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ExtractedField(BaseModel, Generic[T]):
    value: Optional[T] = Field(default=None, description="The extracted value.")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) for this specific field.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief note if text was faint, partially cut off, or missing.",
    )


# --- Refactored Onboarding Model ---
class ThaiIDExtraction(BaseModel):
    id_number: ExtractedField[str] = Field(
        description="13-digit Thai National ID number."
    )
    first_name_en: ExtractedField[Optional[str]] = Field(
        default_factory=ExtractedField, description="First name in English."
    )
    last_name_en: ExtractedField[Optional[str]] = Field(
        default_factory=ExtractedField, description="Last name in English."
    )
    date_of_birth: ExtractedField[Optional[str]] = Field(
        default=None, description="Date of birth in YYYY-MM-DD format"
    )
    expiry_date: ExtractedField[str] = Field(
        description="Expiry date in YYYY-MM-DD format or 'Lifetime'."
    )


# --- Refactored Claims Model ---
class LineItem(BaseModel):
    description: ExtractedField[str] = Field(description="Item description.")
    cost: ExtractedField[float] = Field(description="Cost of this individual item.")


class MedicalReceiptExtraction(BaseModel):
    hospital_name: ExtractedField[Optional[str]] = Field(default_factory=ExtractedField)
    receipt_date: ExtractedField[Optional[str]] = Field(default_factory=ExtractedField)
    items: List[LineItem] = Field(description="List of charges.")
    total_amount: ExtractedField[float] = Field(description="Total balance.")


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
