from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction, LineItem
from app.services.validator import evaluate_thai_id_risk, evaluate_medical_claim_risk


def test_evaluate_thai_id_risk_valid():
    data = ThaiIDExtraction(
        id_number="0000000000000",
        first_name_en="TEST",
        last_name_en="USER",
        date_of_birth="1990-01-01",
        expiry_date="2030-01-01",
    )
    flags, score = evaluate_thai_id_risk(data)
    assert flags == []
    assert score == 0.0


def test_evaluate_thai_id_risk_expired_and_invalid_format():
    data = ThaiIDExtraction(
        id_number="123",
        first_name_en="John",
        last_name_en="Doe",
        date_of_birth="1990-01-01",
        expiry_date="2020-01-01",
    )
    flags, score = evaluate_thai_id_risk(data)
    assert len(flags) == 2
    assert "INVALID_ID_NUMBER_FORMAT" in flags[0]
    assert "DOCUMENT_EXPIRED" in flags[1]
    assert score == 1.0


def test_evaluate_medical_claim_risk_math_mismatch_and_high_risk():
    data = MedicalReceiptExtraction(
        hospital_name="Test Clinic",
        receipt_date="2026-01-01",
        items=[
            LineItem(description="Consultation", cost=500.0),
            LineItem(description="Laser Whitening Treatment", cost=1500.0),
        ],
        total_amount=5000.0,
    )
    flags, score = evaluate_medical_claim_risk(data)
    assert len(flags) == 2
    assert "ARITHMETIC_MISMATCH" in flags[0]
    assert "HIGH_RISK_ITEM_FOUND" in flags[1]
    assert score == 0.9
