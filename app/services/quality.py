"""PII-free document quality assessment grounded in structured extraction evidence."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from app.schemas import (
    DocumentQualityReport,
    ExtractedField,
    ExtractionQualitySignals,
    MedicalReceiptExtraction,
    QualityDisposition,
    ThaiIDExtraction,
)
from app.services.image_processor import ImageQualityAssessment

MIN_FIELD_CONFIDENCE = 0.80
MIN_RESUBMIT_COMPLETENESS = 0.50
MIN_REVIEW_COMPLETENESS = 0.70
MIN_CRITICAL_COMPLETENESS = 0.60


def _is_populated(field: ExtractedField[Any]) -> bool:
    value = field.value
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _iter_extracted_fields(
    value: Any, path: str = ""
) -> Iterator[tuple[str, ExtractedField[Any]]]:
    if isinstance(value, ExtractedField):
        yield path, value
        return
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            child_path = f"{path}.{name}" if path else name
            yield from _iter_extracted_fields(getattr(value, name), child_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_extracted_fields(item, f"{path}[{index}]")


def _field_group(*fields: ExtractedField[Any]) -> tuple[bool, float]:
    populated = bool(fields) and all(_is_populated(field) for field in fields)
    confidence = min((field.confidence for field in fields), default=0.0)
    return populated, confidence


def _critical_groups(
    document_type: str,
    extraction: ThaiIDExtraction | MedicalReceiptExtraction,
) -> dict[str, tuple[bool, float]]:
    if document_type == "thai_id" and isinstance(extraction, ThaiIDExtraction):
        thai_name = _field_group(extraction.first_name_th, extraction.last_name_th)
        english_name = _field_group(extraction.first_name_en, extraction.last_name_en)
        name_group = max(
            (thai_name, english_name), key=lambda group: (group[0], group[1])
        )
        return {
            "identity_number": _field_group(extraction.id_number),
            "name": name_group,
            "date_of_birth": _field_group(extraction.date_of_birth),
            "expiry_date": _field_group(extraction.expiry_date),
            "card_title": _field_group(extraction.visual_checks.has_card_title),
            "portrait": _field_group(extraction.visual_checks.has_portrait_photo),
        }

    if document_type == "medical_receipt" and isinstance(
        extraction, MedicalReceiptExtraction
    ):
        item_fields = [
            field
            for item in extraction.items
            for field in (item.description, item.cost)
        ]
        return {
            "hospital_name": _field_group(extraction.hospital_name),
            "receipt_date": _field_group(extraction.receipt_date),
            "line_items": _field_group(*item_fields),
            "total_amount": _field_group(extraction.total_amount),
        }

    raise ValueError(f"Extraction schema does not match {document_type}.")


def assess_extraction_quality(
    document_type: str,
    extraction: ThaiIDExtraction | MedicalReceiptExtraction,
) -> ExtractionQualitySignals:
    """Measure schema completeness and confidence without copying extracted values."""
    fields = list(_iter_extracted_fields(extraction))
    populated = [(path, field) for path, field in fields if _is_populated(field)]
    low_confidence = [
        path for path, field in populated if field.confidence < MIN_FIELD_CONFIDENCE
    ]
    mean_confidence = (
        sum(field.confidence for _, field in populated) / len(populated)
        if populated
        else 0.0
    )

    critical_groups = _critical_groups(document_type, extraction)
    populated_critical = [
        name for name, (is_present, _) in critical_groups.items() if is_present
    ]
    missing_critical = sorted(set(critical_groups) - set(populated_critical))

    return ExtractionQualitySignals(
        field_count=len(fields),
        populated_field_count=len(populated),
        field_completeness=round(len(populated) / len(fields), 3) if fields else 0.0,
        critical_group_count=len(critical_groups),
        populated_critical_group_count=len(populated_critical),
        critical_completeness=(
            round(len(populated_critical) / len(critical_groups), 3)
            if critical_groups
            else 0.0
        ),
        mean_confidence=round(mean_confidence, 3),
        low_confidence_field_count=len(low_confidence),
        missing_critical_groups=missing_critical,
    )


def build_document_quality_report(
    document_type: str,
    image: ImageQualityAssessment,
    extraction: ThaiIDExtraction | MedicalReceiptExtraction | None,
) -> DocumentQualityReport:
    """Combine advisory pixels with authoritative structured-extraction evidence."""
    image_signals = image.public_signals()
    if extraction is None:
        return DocumentQualityReport(
            disposition=QualityDisposition.REQUEST_RESUBMISSION,
            explanation=(
                "Structured extraction failed after bounded attempts; request a clearer "
                "or complete replacement document."
            ),
            image=image_signals,
        )

    extraction_signals = assess_extraction_quality(document_type, extraction)
    if (
        extraction_signals.field_completeness < MIN_RESUBMIT_COMPLETENESS
        or extraction_signals.critical_completeness < MIN_CRITICAL_COMPLETENESS
    ):
        return DocumentQualityReport(
            disposition=QualityDisposition.REQUEST_RESUBMISSION,
            explanation=(
                "Too little required information was extracted to review the document "
                "safely; request a replacement."
            ),
            image=image_signals,
            extraction=extraction_signals,
        )

    extraction_uncertain = (
        extraction_signals.field_completeness < MIN_REVIEW_COMPLETENESS
        or extraction_signals.critical_completeness < 1.0
        or extraction_signals.mean_confidence < MIN_FIELD_CONFIDENCE
        or extraction_signals.low_confidence_field_count > 0
    )
    if extraction_uncertain or image_signals.advisory_codes:
        return DocumentQualityReport(
            disposition=QualityDisposition.HUMAN_REVIEW,
            explanation=(
                "The document contains sufficient structure to review, but extraction "
                "uncertainty or advisory image signals require human confirmation."
            ),
            image=image_signals,
            extraction=extraction_signals,
        )

    return DocumentQualityReport(
        disposition=QualityDisposition.CONTINUE,
        explanation=(
            "Structured extraction is sufficiently complete and confident; image "
            "heuristics raised no advisory signal."
        ),
        image=image_signals,
        extraction=extraction_signals,
    )
