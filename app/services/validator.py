from datetime import datetime
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction


def evaluate_thai_id_risk(data: ThaiIDExtraction) -> tuple[list[str], float]:
    """
    Evaluates risk vectors on parsed Thai ID data using strict rule checks.
    Returns a list of flags and a dynamic risk weight delta.
    """
    flags = []
    risk_score = 0.0

    # 1. Structural Identity Guardrail: Check length of ID
    clean_id = "".join(data.id_number.split())  # Strip accidental whitespaces
    if len(clean_id) != 13 or not clean_id.isdigit():
        flags.append(
            "INVALID_ID_NUMBER_FORMAT: Thai ID must be exactly 13 numeric digits."
        )
        risk_score += 0.6

    # 2. Compliance Guardrail: Expiration Evaluation
    if data.expiry_date.strip().lower() != "lifetime":
        try:
            # Parse date fields safely using the standard format string
            expiry_dt = datetime.strptime(data.expiry_date, "%Y-%m-%d").date()
            current_dt = datetime.now().date()  # Current year: 2026

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

    # Cap risk score boundaries safely
    return flags, min(risk_score, 1.0)


def evaluate_medical_claim_risk(
    data: MedicalReceiptExtraction,
) -> tuple[list[str], float]:
    """
    Evaluates structural integrity risk checks on medical insurance claims documents.
    """
    flags = []
    risk_score = 0.0

    # 1. Financial Guardrail: Mathematical Line-Item Verification
    # Loop through items and aggregate float values to crosscheck balance sheets
    calculated_total = sum(item.cost for item in data.items)

    # Allow a minor epsilon floating-point tolerance of 0.01 instead of direct float mapping comparisons
    if abs(calculated_total - data.total_amount) > 0.01:
        flags.append(
            f"ARITHMETIC_MISMATCH: Stated invoice total ({data.total_amount}) does not match "
            f"the calculated sum of line items ({calculated_total})."
        )
        risk_score += 0.5

    # 2. Risk Policy Guardrail: Flag prohibited service items (e.g., non-covered aesthetic/cosmetic items)
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
            break  # Flag once is enough to trigger policy alerts

    return flags, min(risk_score, 1.0)
