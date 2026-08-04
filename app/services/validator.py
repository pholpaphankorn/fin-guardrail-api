from datetime import datetime
from typing import Any, Tuple
from app.schemas import ExtractedField, ThaiIDExtraction, MedicalReceiptExtraction

MIN_CONFIDENCE = 0.9


def is_valid_thai_id_checksum(id_number: str) -> bool:
    """
    Validates a 13-digit Thai National ID using the Modulus 11 algorithm.
    Detects single-digit LLM OCR hallucinations and mathematical misreads.
    """
    clean_id = "".join(id_number.split())

    if len(clean_id) != 13 or not clean_id.isdigit():
        return False

    digits = [int(d) for d in clean_id]

    # Calculate Modulus 11 checksum across the first 12 digits
    total = sum(digits[i] * (13 - i) for i in range(12))
    expected_check_digit = (11 - (total % 11)) % 10

    # Validate against the 13th digit
    return digits[12] == expected_check_digit


def check_field_risk(
    field: ExtractedField[Any],
    field_name: str,
    weight: float,
    min_confidence: float = MIN_CONFIDENCE,
    is_boolean_check: bool = False,
) -> Tuple[list[str], float]:
    """
    Evaluates value presence and extraction confidence for a single ExtractedField.
    Returns generated risk flags and calculated risk score penalty.
    """
    flags = []
    penalty = 0.0
    reasoning_suffix = f" (Note: {field.reasoning})" if field.reasoning else ""

    # Case A: Value Failure (Missing text or False visual check)
    if is_boolean_check and field.value is False:
        flags.append(
            f"MISSING_VISUAL_ANCHOR: Visual check '{field_name}' failed.{reasoning_suffix}")
        penalty += weight  # Full field weight penalty

    elif not is_boolean_check and (field.value is None or str(field.value).strip() == ""):
        flags.append(
            f"MISSING_FIELD_VALUE: Field '{field_name}' could not be extracted.{reasoning_suffix}")
        penalty += weight  # Full field weight penalty

    # Case B: Low Confidence Penalty (Value exists, but Vision LLM is uncertain)
    elif field.confidence < min_confidence:
        flags.append(
            f"LOW_FIELD_CONFIDENCE: Field '{field_name}' confidence ({field.confidence:.2f}) "
            f"is below threshold ({min_confidence:.2f}).{reasoning_suffix}"
        )
        penalty += weight * 0.5  # Partial weight penalty for uncertainty

    return flags, penalty


def evaluate_thai_id_risk(data: ThaiIDExtraction) -> tuple[list[str], float]:
    flags = []
    risk_score = 0.0

    # Field Weights Configuration
    # Total combined risk capped at 1.0
    FIELD_CONFIGS = [
        # (field_object, field_name, weight, min_confidence, is_boolean)
        # --- Visual Checks ---
        (data.visual_checks.has_card_title,
         "has_card_title", 1, MIN_CONFIDENCE, True),
        (data.visual_checks.has_garuda_emblem,
         "has_garuda_emblem", 0.30, MIN_CONFIDENCE, True),
        (data.visual_checks.has_microchip,
         "has_microchip", 0.40, MIN_CONFIDENCE, True),
        (data.visual_checks.has_portrait_photo,
         "has_portrait_photo", 1, MIN_CONFIDENCE, True),
        (data.visual_checks.has_barcode, "has_barcode", 0.20, MIN_CONFIDENCE, True),

        # --- Core Critical Fields ---
        (data.id_number, "id_number", 1, MIN_CONFIDENCE, False),
        (data.expiry_date, "expiry_date", 1, MIN_CONFIDENCE, False),

        # --- Secondary Personal Info ---
        (data.first_name_th, "first_name_th", 1, MIN_CONFIDENCE, False),
        (data.last_name_th, "last_name_th", 1, MIN_CONFIDENCE, False),
        (data.first_name_en, "first_name_en", 1, MIN_CONFIDENCE, False),
        (data.last_name_en, "last_name_en", 1, MIN_CONFIDENCE, False),
        (data.date_of_birth, "date_of_birth", 1, MIN_CONFIDENCE, False),
        (data.address_th, "address_th", 1, MIN_CONFIDENCE, False),
        (data.issue_date, "issue_date", 0.15, MIN_CONFIDENCE, False),
        (data.issuing_officer_th, "issuing_officer_th", 0.10, MIN_CONFIDENCE, False),
        (data.religion_th, "religion_th", 0.05, MIN_CONFIDENCE, False),
    ]

    # 1. Run Standardized Field Evaluation Loop
    for field_obj, field_name, weight, min_conf, is_bool in FIELD_CONFIGS:
        field_flags, penalty = check_field_risk(
            field=field_obj,
            field_name=field_name,
            weight=weight,
            min_confidence=min_conf,
            is_boolean_check=is_bool,
        )
        flags.extend(field_flags)
        risk_score += penalty

    # 2. Specific Deterministic Rule: Checksum Check (If ID exists)
    raw_id = data.id_number.value or ""
    clean_id = "".join(raw_id.split())
    if clean_id:
        if len(clean_id) != 13 or not clean_id.isdigit():
            flags.append(
                "INVALID_ID_NUMBER_FORMAT: Thai ID must be exactly 13 numeric digits.")
            risk_score += 0.6
        elif not is_valid_thai_id_checksum(clean_id):
            flags.append(
                f"ID_CHECKSUM_FAILED: Extracted ID ({clean_id}) failed Modulus 11 validation."
            )
            risk_score += 0.7

    # 3. Specific Deterministic Rule: Document Expiration Check
    raw_expiry = data.expiry_date.value or ""
    if raw_expiry and raw_expiry.strip().lower() != "lifetime":
        try:
            expiry_dt = datetime.strptime(raw_expiry, "%Y-%m-%d").date()
            if expiry_dt < datetime.now().date():
                flags.append(
                    f"DOCUMENT_EXPIRED: Identification card expired on {raw_expiry}.")
                risk_score += 0.8
        except ValueError:
            flags.append("DATE_PARSING_ERROR: Expiry date format invalid.")
            risk_score += 0.4

    return flags, min(risk_score, 1.0)


def evaluate_medical_claim_risk(
    data: MedicalReceiptExtraction,
) -> tuple[list[str], float]:
    """
    Evaluates structural integrity risk checks on medical insurance claims documents.
    """
    flags = []
    risk_score = 0.0

    # 1. Vision LLM Field-Level Confidence Guardrail
    total_confidence = data.total_amount.confidence
    if total_confidence < 0.80:
        reasoning_str = (
            f" Note: {data.total_amount.reasoning}"
            if data.total_amount.reasoning
            else ""
        )
        flags.append(
            f"LOW_TOTAL_CONFIDENCE: Vision LLM extraction confidence for total_amount ({total_confidence:.2f}) "
            f"is below safety threshold (0.80).{reasoning_str}"
        )
        risk_score += 0.4

    # Check for any low-confidence itemized costs
    low_confidence_items = [
        item for item in data.items if item.cost.confidence < 0.75]
    if low_confidence_items:
        flags.append(
            f"LOW_ITEM_CONFIDENCE: Found {len(low_confidence_items)} line item(s) "
            f"with low extraction confidence (<0.75)."
        )
        risk_score += 0.3

    # 2. Financial Guardrail: Mathematical Line-Item Verification
    calculated_total = sum(item.cost.value or 0.0 for item in data.items)
    stated_total = data.total_amount.value or 0.0

    if abs(calculated_total - stated_total) > 0.01:
        flags.append(
            f"ARITHMETIC_MISMATCH: Stated invoice total ({stated_total}) does not match "
            f"the calculated sum of line items ({calculated_total})."
        )
        risk_score += 0.5

    # 3. Risk Policy Guardrail: Flag prohibited service items
    high_risk_keywords = [
        "cosmetic",
        "plastic surgery",
        "laser",
        "whitening",
        "aesthetic",
        "ศัลยกรรม",
        "เลเซอร์",
    ]

    for item in data.items:
        desc_str = item.description.value or ""
        desc_lower = desc_str.lower()
        if any(keyword in desc_lower for keyword in high_risk_keywords):
            flags.append(
                f"HIGH_RISK_ITEM_FOUND: Claim item '{desc_str}' matches non-covered coverage policies."
            )
            risk_score += 0.4
            break

    return flags, min(risk_score, 1.0)


def calculate_status_and_reasoning(risk_score: float) -> tuple[str, str]:
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


def build_unreadable_document_response(doc_type: str, flag_reason: str) -> dict:
    """Returns a standard HTTP 200 rejection response when pre-processing or extraction fails."""
    return {
        "document_type": doc_type,
        "status": "REJECTED",
        "extracted_data": {},
        "validation_flags": [flag_reason],
        "risk_score": 1.0,
        "reasoning": "Document failed pre-processing visual quality or legibility guardrails.",
    }
