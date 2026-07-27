from datetime import datetime
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction


def evaluate_thai_id_risk(data: ThaiIDExtraction) -> tuple[list[str], float]:
    """
    Evaluates risk vectors on parsed Thai ID data using strict rule checks.
    Returns a list of flags and a dynamic risk weight delta.
    """
    flags = []
    risk_score = 0.0

    # 1. Vision LLM Confidence Guardrail
    if data.confidence_score < 0.75:
        flags.append(
            f"LOW_MODEL_CONFIDENCE: Vision LLM extraction confidence ({data.confidence_score:.2f}) "
            f"is below safety threshold (0.75)."
        )
        risk_score += 0.5

    # 2. Structural Identity Guardrail: Check length of ID
    clean_id = "".join(data.id_number.split())  # Strip accidental whitespaces
    if len(clean_id) != 13 or not clean_id.isdigit():
        flags.append(
            "INVALID_ID_NUMBER_FORMAT: Thai ID must be exactly 13 numeric digits."
        )
        risk_score += 0.6

    # 3. Compliance Guardrail: Expiration Evaluation
    if data.expiry_date.strip().lower() != "lifetime":
        try:
            expiry_dt = datetime.strptime(data.expiry_date, "%Y-%m-%d").date()
            current_dt = datetime.now().date()

            if expiry_dt < current_dt:
                flags.append(
                    f"DOCUMENT_EXPIRED: Identification card expired on {data.expiry_date}"
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

    # 1. Vision LLM Confidence Guardrail
    if data.confidence_score < 0.75:
        flags.append(
            f"LOW_MODEL_CONFIDENCE: Vision LLM extraction confidence ({data.confidence_score:.2f}) "
            f"is below safety threshold (0.75)."
        )
        risk_score += 0.5

    # 2. Financial Guardrail: Mathematical Line-Item Verification
    calculated_total = sum(item.cost for item in data.items)

    if abs(calculated_total - data.total_amount) > 0.01:
        flags.append(
            f"ARITHMETIC_MISMATCH: Stated invoice total ({data.total_amount}) does not match "
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
        desc_lower = item.description.lower()
        if any(keyword in desc_lower for keyword in high_risk_keywords):
            flags.append(
                f"HIGH_RISK_ITEM_FOUND: Claim item '{item.description}' matches non-covered coverage policies."
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
