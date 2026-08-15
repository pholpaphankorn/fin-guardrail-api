import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.schemas import (
    MedicalReceiptExtraction,
    QualityDisposition,
    ThaiIDExtraction,
)
from app.services.image_processor import (
    ImageQualityAssessment,
    evaluate_image_quality_dependency,
)
from app.services.quality import (
    assess_extraction_quality,
    build_document_quality_report,
)


def load_extraction(filename: str, schema):
    payload = json.loads((Path("data/mock_jsons") / filename).read_text("utf-8"))
    return schema.model_validate(payload)


def image_quality(
    *, blur_suspected: bool = False, low_resolution_suspected: bool = False
) -> ImageQualityAssessment:
    return ImageQualityAssessment(
        image_bytes=b"synthetic-image",
        width=1200,
        height=800,
        focus_score=20.0 if blur_suspected else 180.0,
        blur_suspected=blur_suspected,
        low_resolution_suspected=low_resolution_suspected,
    )


@pytest.mark.unit
def test_complete_confident_extraction_can_continue():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)

    report = build_document_quality_report("thai_id", image_quality(), extraction)

    assert report.disposition == QualityDisposition.CONTINUE
    assert report.extraction is not None
    assert report.extraction.critical_completeness == 1.0
    assert report.extraction.mean_confidence >= 0.9


@pytest.mark.unit
def test_blur_is_advisory_and_routes_successful_extraction_to_review():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)

    report = build_document_quality_report(
        "thai_id", image_quality(blur_suspected=True), extraction
    )

    assert report.disposition == QualityDisposition.HUMAN_REVIEW
    assert report.image.advisory_codes == ["POSSIBLE_BLUR"]
    assert report.extraction is not None
    assert report.extraction.critical_completeness == 1.0


@pytest.mark.unit
def test_low_processed_resolution_is_advisory_and_routes_to_review():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)

    report = build_document_quality_report(
        "thai_id", image_quality(low_resolution_suspected=True), extraction
    )

    assert report.disposition == QualityDisposition.HUMAN_REVIEW
    assert report.image.advisory_codes == ["LOW_PROCESSED_RESOLUTION"]


@pytest.mark.unit
def test_low_confidence_critical_text_routes_to_review_not_rejection():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)
    extraction.id_number.confidence = 0.55

    report = build_document_quality_report("thai_id", image_quality(), extraction)

    assert report.disposition == QualityDisposition.HUMAN_REVIEW
    assert report.extraction is not None
    assert report.extraction.low_confidence_field_count == 1


@pytest.mark.unit
def test_missing_critical_groups_requests_resubmission():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)
    for field in (
        extraction.id_number,
        extraction.first_name_th,
        extraction.last_name_th,
        extraction.first_name_en,
        extraction.last_name_en,
        extraction.date_of_birth,
        extraction.expiry_date,
    ):
        field.value = None

    report = build_document_quality_report("thai_id", image_quality(), extraction)

    assert report.disposition == QualityDisposition.REQUEST_RESUBMISSION
    assert report.extraction is not None
    assert report.extraction.critical_completeness < 0.6
    assert "identity_number" in report.extraction.missing_critical_groups
    assert "name" in report.extraction.missing_critical_groups


@pytest.mark.unit
def test_receipt_quality_uses_line_items_as_critical_evidence():
    extraction = load_extraction("mock_medical_receipt.json", MedicalReceiptExtraction)

    complete = assess_extraction_quality("medical_receipt", extraction)
    extraction.items = []
    missing_items = assess_extraction_quality("medical_receipt", extraction)

    assert complete.critical_completeness == 1.0
    assert "line_items" in missing_items.missing_critical_groups


@pytest.mark.unit
def test_report_never_copies_extracted_values():
    extraction = load_extraction("mock_thai_id.json", ThaiIDExtraction)

    report = build_document_quality_report(
        "thai_id", image_quality(), extraction
    ).model_dump_json()

    assert extraction.id_number.value not in report
    assert extraction.address_th.value not in report


@pytest.mark.asyncio
async def test_noise_cannot_pass_when_structured_extraction_fails():
    noise = np.random.default_rng(7).integers(0, 256, (900, 1200), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", noise)
    image = await evaluate_image_quality_dependency(resized_bytes=encoded.tobytes())

    report = build_document_quality_report("thai_id", image, None)

    assert image.blur_suspected is False
    assert report.disposition == QualityDisposition.REQUEST_RESUBMISSION
    assert report.extraction is None
