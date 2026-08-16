from datetime import datetime, timedelta
from app.schemas import (
    ExtractedField,
    ThaiIDExtraction,
    ThaiIDVisualChecks,
    MedicalReceiptExtraction,
    LineItem,
)
from app.services.validator import (
    evaluate_thai_id_risk,
    evaluate_medical_claim_risk,
    calculate_status_and_reasoning,
    build_unreadable_document_response,
)


def extracted(value, confidence=0.95):
    return ExtractedField(value=value, confidence=confidence)


def make_thai_id(**overrides):
    fields = {
        "visual_checks": ThaiIDVisualChecks(
            has_card_title=extracted(True),
            has_garuda_emblem=extracted(True),
            has_microchip=extracted(True),
            has_portrait_photo=extracted(True),
            has_barcode=extracted(True),
        ),
        "id_number": extracted("1234567890121"),
        "first_name_th": extracted("TEST"),
        "last_name_th": extracted("USER"),
        "first_name_en": extracted("TEST"),
        "last_name_en": extracted("Dee"),
        "date_of_birth": extracted("1990-01-01"),
        "address_th": extracted("กรุงเทพมหานคร"),
        "issue_date": extracted("2020-01-01"),
        "expiry_date": extracted("2030-01-01"),
        "issuing_officer_th": extracted("เจ้าหน้าที่ทดสอบ"),
        "religion_th": extracted("พุทธ"),
    }
    fields.update(overrides)
    return ThaiIDExtraction(**fields)


def make_receipt(*, items, total_amount, total_confidence=0.90):
    return MedicalReceiptExtraction(
        hospital_name=extracted("City Hospital"),
        receipt_date=extracted("2026-03-01"),
        items=[
            LineItem(description=extracted(description), cost=extracted(cost))
            for description, cost in items
        ],
        total_amount=extracted(total_amount, total_confidence),
    )


class TestEvaluateThaiIDRisk:

    def test_thai_id_happy_case_clean_approval(self):
        """Happy Case: Perfectly valid Thai ID (with valid Modulus 11 checksum) produces zero flags and 0.0 risk score."""
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        valid_id = make_thai_id(
            id_number=extracted("1 2345 67890 12 1"),
            expiry_date=extracted(future_date),
        )

        flags, risk_score = evaluate_thai_id_risk(valid_id)

        assert flags == []
        assert risk_score == 0.0

    def test_thai_id_edge_case_lifetime_expiry(self):
        """Edge Case: 'lifetime' expiry date string with valid checksum is parsed properly without flags."""
        valid_lifetime_id = make_thai_id(expiry_date=extracted("LIFETIME"))

        flags, risk_score = evaluate_thai_id_risk(valid_lifetime_id)

        assert flags == []
        assert risk_score == 0.0

    def test_thai_id_failed_case_checksum_failure(self):
        """Failed Case: 13-digit numeric string that fails Modulus 11 check triggers ID_CHECKSUM_FAILED flag."""
        invalid_checksum_id = make_thai_id(
            id_number=extracted("1234567890123"),
        )

        flags, risk_score = evaluate_thai_id_risk(invalid_checksum_id)

        assert len(flags) == 1
        assert "ID_CHECKSUM_FAILED" in flags[0]
        assert risk_score == 0.7

    def test_thai_id_failed_case_repeated_placeholder_number(self):
        """A mathematically checksum-valid placeholder must never be accepted."""
        placeholder_id = make_thai_id(id_number=extracted("0000000000000"))

        flags, risk_score = evaluate_thai_id_risk(placeholder_id)

        assert len(flags) == 1
        assert "PLACEHOLDER_ID_NUMBER" in flags[0]
        assert risk_score == 0.7

    def test_thai_id_failed_case_expired_and_low_confidence(self):
        """Failed Case: Expired card + low confidence accumulates risk flags."""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        expired_id = make_thai_id(
            id_number=extracted("1234567890121", confidence=0.60),
            expiry_date=extracted(past_date),
        )

        flags, risk_score = evaluate_thai_id_risk(expired_id)

        assert len(flags) == 2
        assert any("LOW_FIELD_CONFIDENCE" in f for f in flags)
        assert any("DOCUMENT_EXPIRED" in f for f in flags)
        assert risk_score == 1.0  # 0.5 + 0.8 = 1.3 capped at 1.0

    def test_thai_id_failed_case_invalid_format_and_date_error(self):
        """Failed Case: Non-numeric ID number and malformed expiry date string."""
        bad_id = make_thai_id(
            id_number=extracted("12345ABC"),
            expiry_date=extracted("2028/12/31"),
        )

        flags, risk_score = evaluate_thai_id_risk(bad_id)

        assert len(flags) == 2
        assert any("INVALID_ID_NUMBER_FORMAT" in f for f in flags)
        assert any("DATE_PARSING_ERROR" in f for f in flags)
        assert risk_score == 1.0  # 0.6 + 0.4 = 1.0


class TestEvaluateMedicalClaimRisk:

    def test_medical_claim_happy_case_clean_approval(self):
        """Happy Case: Perfectly matching line items and total with clean policy items."""
        receipt = make_receipt(
            items=[("Consultation", 500.0), ("Medication", 150.0)],
            total_amount=650.0,
        )

        flags, risk_score = evaluate_medical_claim_risk(receipt)

        assert flags == []
        assert risk_score == 0.0

    def test_medical_claim_failed_case_arithmetic_mismatch(self):
        """Failed Case: Line items sum does not equal total amount."""
        receipt = make_receipt(
            items=[("Blood Test", 1000.0)],
            total_amount=1200.0,
        )

        flags, risk_score = evaluate_medical_claim_risk(receipt)

        assert len(flags) == 1
        assert "ARITHMETIC_MISMATCH" in flags[0]
        assert risk_score == 0.5

    def test_medical_claim_edge_case_high_risk_keywords_thai_and_english(self):
        """Edge Case: Detects non-covered treatment keywords in English and Thai."""
        receipt_en = make_receipt(
            items=[("Skin Whitening Treatment", 3000.0)],
            total_amount=3000.0,
        )

        receipt_th = make_receipt(
            items=[("คอร์ส เลเซอร์ หน้าใส", 3000.0)],
            total_amount=3000.0,
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
