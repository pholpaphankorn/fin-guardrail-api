from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ExtractedField(BaseModel, Generic[T]):
    value: Optional[T] = Field(
        default=None, description="The extracted value.")
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


class ThaiIDVisualChecks(BaseModel):
    has_card_title: ExtractedField[bool] = Field(
        description="True if top header 'บัตรประจำตัวประชาชน' or 'Thai National ID Card' is visible."
    )
    has_garuda_emblem: ExtractedField[bool] = Field(
        description="True if the official Garuda emblem on top-left is visible."
    )
    has_microchip: ExtractedField[bool] = Field(
        description="True if the metallic smart chip on middle-left is visible."
    )
    has_portrait_photo: ExtractedField[bool] = Field(
        description="True if the holder's headshot photo on the right side is visible."
    )
    has_barcode: ExtractedField[bool] = Field(
        description="True if the vertical barcode on the left margin is visible."
    )


class ThaiIDExtraction(BaseModel):
    # Visual Anchors (Required Keys)
    visual_checks: ThaiIDVisualChecks

    # Core Required Data Fields (Keys are REQUIRED in JSON, value can be string or null)
    id_number: ExtractedField[str] = Field(
        description="13-digit Thai National ID number."
    )
    first_name_th: ExtractedField[str] = Field(
        description="First name in Thai."
    )
    last_name_th: ExtractedField[str] = Field(
        description="Last name in Thai."
    )
    first_name_en: ExtractedField[str] = Field(
        description="First name in English."
    )
    last_name_en: ExtractedField[str] = Field(
        description="Last name in English."
    )
    date_of_birth: ExtractedField[str] = Field(
        description="Date of birth in YYYY-MM-DD format."
    )
    address_th: ExtractedField[str] = Field(
        description="Full residential address in Thai."
    )
    issue_date: ExtractedField[str] = Field(
        description="Date of issue in YYYY-MM-DD format."
    )
    expiry_date: ExtractedField[str] = Field(
        description="Expiry date in YYYY-MM-DD format or 'Lifetime'."
    )
    issuing_officer_th: ExtractedField[str] = Field(
        description="Name and title of issuing officer (เจ้าพนักงานออกบัตร)."
    )

    religion_th: ExtractedField[str] = Field(
        description="Religion stated in Thai (e.g., พุทธ, คริสต์, อิสลาม).",
    )
# --- Refactored Claims Model ---


class LineItem(BaseModel):
    description: ExtractedField[str] = Field(description="Item description.")
    cost: ExtractedField[float] = Field(
        description="Cost of this individual item.")


class MedicalReceiptExtraction(BaseModel):
    hospital_name: ExtractedField[Optional[str]] = Field(
        default_factory=ExtractedField)
    receipt_date: ExtractedField[Optional[str]] = Field(
        default_factory=ExtractedField)
    items: List[LineItem] = Field(description="List of charges.")
    total_amount: ExtractedField[float] = Field(description="Total balance.")


# --- Final System Response Model ---
class RiskAssessmentResponse(BaseModel):
    document_type: str = Field(description="'thai_id' or 'medical_receipt'")
    status: str = Field(
        description="APPROVED, FLAGGED_FOR_REVIEW, or REJECTED")
    extracted_data: dict = Field(
        description="The raw data extracted by the Vision LLM")
    validation_flags: List[str] = Field(
        description="List of issues caught by deterministic code rule checks"
    )
    risk_score: float = Field(
        description="Calculated risk level between 0.0 (Safe) and 1.0 (Critical)"
    )
    reasoning: str = Field(
        description="Detailed text explaining the verdict status")
