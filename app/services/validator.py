from datetime import datetime
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction


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


def evaluate_thai_id_risk(data: ThaiIDExtraction) -> tuple[list[str], float]:
    """
    Evaluates risk vectors on parsed Thai ID data using strict rule checks.
    Returns a list of flags and a dynamic risk weight delta.
    """
    flags = []
    risk_score = 0.0

    # 1. Targeted Field Confidence Check: Critical ID Number
    if data.id_number.confidence < 0.85:
        reasoning_str = (
            f" Note: {data.id_number.reasoning}" if data.id_number.reasoning else ""
        )
        flags.append(
            f"LOW_ID_CONFIDENCE: Vision LLM is uncertain about the ID number "
            f"({data.id_number.confidence:.2f}).{reasoning_str}"
        )
        risk_score += 0.5

    # 2. Critical Expiry Date Confidence
    if data.expiry_date.confidence < 0.70:
        reasoning_str = (
            f" Note: {data.expiry_date.reasoning}" if data.expiry_date.reasoning else ""
        )
        flags.append(
            f"LOW_EXPIRY_CONFIDENCE: Model struggled reading expiry date "
            f"({data.expiry_date.confidence:.2f}).{reasoning_str}"
        )
        risk_score += 0.3

    # 3. Structural & Mathematical Identity Guardrails
    raw_id = data.id_number.value or ""
    clean_id = "".join(raw_id.split())

    # Format Check
    if len(clean_id) != 13 or not clean_id.isdigit():
        flags.append(
            "INVALID_ID_NUMBER_FORMAT: Thai ID must be exactly 13 numeric digits."
        )
        risk_score += 0.6
    # Modulus 11 Checksum Verification (Catches Vision LLM Hallucinations)
    elif not is_valid_thai_id_checksum(clean_id):
        flags.append(
            f"ID_CHECKSUM_FAILED: Extracted ID ({clean_id}) failed Modulus 11 validation. "
            f"Possible LLM OCR hallucination or invalid ID number sequence."
        )
        risk_score += 0.7

    # 4. Compliance Guardrail: Expiration Evaluation
    raw_expiry = data.expiry_date.value or ""
    if raw_expiry.strip().lower() != "lifetime":
        try:
            expiry_dt = datetime.strptime(raw_expiry, "%Y-%m-%d").date()
            current_dt = datetime.now().date()

            if expiry_dt < current_dt:
                flags.append(
                    f"DOCUMENT_EXPIRED: Identification card expired on {raw_expiry}"
                )
                risk_score += 0.8
        except ValueError:
            flags.append(
                "DATE_PARSING_ERROR: Expiry date does not match expected YYYY-MM-DD pattern."
            )
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
    low_confidence_items = [item for item in data.items if item.cost.confidence < 0.75]
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
