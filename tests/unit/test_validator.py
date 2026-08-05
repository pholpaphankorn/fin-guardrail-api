from datetime import datetime, timedelta
from unittest.mock import patch
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction, LineItem
from app.services.validator import (
    evaluate_thai_id_risk,
    evaluate_medical_claim_risk,
    calculate_status_and_reasoning,
    build_unreadable_document_response,
)


class TestEvaluateThaiIDRisk:

    def test_thai_id_happy_case_clean_approval(self):
        """Happy Case: Perfectly valid Thai ID (with valid Modulus 11 checksum) produces zero flags and 0.0 risk score."""
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        valid_id = ThaiIDExtraction(
            id_number="1 2345 67890 12 1",  # Mathematically valid checksum sequence
            first_name_en="TEST",
            last_name_en="Dee",
            date_of_birth="1990-01-01",
            expiry_date=future_date,
            confidence_score=0.95,
        )

        flags, risk_score = evaluate_thai_id_risk(valid_id)

        assert flags == []
        assert risk_score == 0.0

    def test_thai_id_edge_case_lifetime_expiry(self):
        """Edge Case: 'lifetime' expiry date string with valid checksum is parsed properly without flags."""
        valid_lifetime_id = ThaiIDExtraction(
            id_number="1234567890121",  # Valid checksum
            first_name_en="Jane",
            last_name_en="Doe",
            date_of_birth="1950-01-01",
            expiry_date="LIFETIME",  # Case insensitive test
            confidence_score=0.88,
        )

        flags, risk_score = evaluate_thai_id_risk(valid_lifetime_id)

        assert flags == []
        assert risk_score == 0.0

    def test_thai_id_failed_case_checksum_failure(self):
        """Failed Case: 13-digit numeric string that fails Modulus 11 check triggers ID_CHECKSUM_FAILED flag."""
        invalid_checksum_id = ThaiIDExtraction(
            id_number="1234567890123",  # 13 digits, but check digit 3 should be 1
            first_name_en="TEST",
            last_name_en="Dee",
            date_of_birth="1990-01-01",
            expiry_date="2030-01-01",
            confidence_score=0.95,
        )

        flags, risk_score = evaluate_thai_id_risk(invalid_checksum_id)

        assert len(flags) == 1
        assert "ID_CHECKSUM_FAILED" in flags[0]
        assert risk_score == 0.7

    def test_thai_id_failed_case_expired_and_low_confidence(self):
        """Failed Case: Expired card + low confidence accumulates risk flags."""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        expired_id = ThaiIDExtraction(
            id_number="1234567890121",  # Valid checksum
            first_name_en="John",
            last_name_en="Doe",
            date_of_birth="1980-01-01",
            expiry_date=past_date,
            confidence_score=0.60,  # Below 0.75 threshold
        )

        flags, risk_score = evaluate_thai_id_risk(expired_id)

        assert len(flags) == 2
        assert any("LOW_MODEL_CONFIDENCE" in f for f in flags)
        assert any("DOCUMENT_EXPIRED" in f for f in flags)
        assert risk_score == 1.0  # 0.5 + 0.8 = 1.3 capped at 1.0

    def test_thai_id_failed_case_invalid_format_and_date_error(self):
        """Failed Case: Non-numeric ID number and malformed expiry date string."""
        bad_id = ThaiIDExtraction(
            id_number="12345ABC",  # Short and non-digit
            first_name_en="John",
            last_name_en="Doe",
            date_of_birth="1980-01-01",
            expiry_date="2028/12/31",  # Wrong delimiter format
            confidence_score=0.85,
        )

        flags, risk_score = evaluate_thai_id_risk(bad_id)

        assert len(flags) == 2
        assert any("INVALID_ID_NUMBER_FORMAT" in f for f in flags)
        assert any("DATE_PARSING_ERROR" in f for f in flags)
        assert risk_score == 1.0  # 0.6 + 0.4 = 1.0


class TestEvaluateMedicalClaimRisk:

    def test_medical_claim_happy_case_clean_approval(self):
        """Happy Case: Perfectly matching line items and total with clean policy items."""
        receipt = MedicalReceiptExtraction(
            hospital_name="City Hospital",
            receipt_date="2026-03-01",
            items=[
                LineItem(description="Consultation", cost=500.0),
                LineItem(description="Medication", cost=150.0),
            ],
            total_amount=650.0,
            confidence_score=0.90,
        )

        flags, risk_score = evaluate_medical_claim_risk(receipt)

        assert flags == []
        assert risk_score == 0.0

    def test_medical_claim_failed_case_arithmetic_mismatch(self):
        """Failed Case: Line items sum does not equal total amount."""
        receipt = MedicalReceiptExtraction(
            hospital_name="City Hospital",
            receipt_date="2026-03-01",
            items=[
                LineItem(description="Blood Test", cost=1000.0),
            ],
            total_amount=1200.0,  # Mismatch by 200.0
            confidence_score=0.80,
        )

        flags, risk_score = evaluate_medical_claim_risk(receipt)

        assert len(flags) == 1
        assert "ARITHMETIC_MISMATCH" in flags[0]
        assert risk_score == 0.5

    def test_medical_claim_edge_case_high_risk_keywords_thai_and_english(self):
        """Edge Case: Detects non-covered treatment keywords in English and Thai."""
        receipt_en = MedicalReceiptExtraction(
            hospital_name="Aesthetic Clinic",
            receipt_date="2026-03-01",
            items=[LineItem(description="Skin Whitening Treatment", cost=3000.0)],
            total_amount=3000.0,
            confidence_score=0.85,
        )

        receipt_th = MedicalReceiptExtraction(
            hospital_name="Aesthetic Clinic",
            receipt_date="2026-03-01",
            items=[LineItem(description="คอร์ส เลเซอร์ หน้าใส", cost=3000.0)],
            total_amount=3000.0,
            confidence_score=0.85,
        )

        flags_en, risk_en = evaluate_medical_claim_risk(receipt_en)
        flags_th, risk_th = evaluate_medical_claim_risk(receipt_th)

        assert any("HIGH_RISK_ITEM_FOUND" in f for f in flags_en)
        assert risk_en == 0.4

        assert any("HIGH_RISK_ITEM_FOUND" in f for f in flags_th)
        assert risk_th == 0.4


class TestRoutingAndResponseHelpers:

    def test_calculate_status_and_reasoning_thresholds(self):
        """Happy & Edge Cases: Verifies boundary routing logic for statuses."""
        # Risk == 0.0 -> APPROVED
        status, _ = calculate_status_and_reasoning(0.0)
        assert status == "APPROVED"

        # 0.0 < Risk < 0.7 -> FLAGGED_FOR_REVIEW
        status_low, _ = calculate_status_and_reasoning(0.1)
        status_mid, _ = calculate_status_and_reasoning(0.69)
        assert status_low == "FLAGGED_FOR_REVIEW"
        assert status_mid == "FLAGGED_FOR_REVIEW"

        # Risk >= 0.7 -> REJECTED
        status_high, _ = calculate_status_and_reasoning(0.7)
        status_max, _ = calculate_status_and_reasoning(1.0)
        assert status_high == "REJECTED"
        assert status_max == "REJECTED"

    def test_build_unreadable_document_response(self):
        """Happy Case: Formatting check for standardized business rejection response."""
        resp = build_unreadable_document_response("thai_id", "CORRUPTED_FILE")

        assert resp["document_type"] == "thai_id"
        assert resp["status"] == "REJECTED"
        assert resp["risk_score"] == 1.0
        assert resp["extracted_data"] == {}
        assert resp["validation_flags"] == ["CORRUPTED_FILE"]
