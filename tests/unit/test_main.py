import json
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.main import app
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from app.services.image_processor import (
    ImageQualityAssessment,
    evaluate_image_quality_dependency,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def create_dummy_image_bytes(extension: str = ".jpg") -> bytes:
    """Return minimalist valid image bytes for router testing."""
    import cv2
    import numpy as np

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img.fill(200)
    _, buf = cv2.imencode(extension, img)
    return buf.tobytes()


def load_mock_extraction(filename: str, schema):
    mock_path = Path("data/mock_jsons") / filename
    return schema.model_validate(json.loads(mock_path.read_text(encoding="utf-8")))


def override_image_quality(
    *, blur_suspected: bool = False, low_resolution_suspected: bool = False
):
    async def _override() -> ImageQualityAssessment:
        return ImageQualityAssessment(
            image_bytes=b"image_bytes",
            width=1200,
            height=800,
            focus_score=20.0 if blur_suspected else 180.0,
            blur_suspected=blur_suspected,
            low_resolution_suspected=low_resolution_suspected,
        )

    return _override


@pytest.mark.asyncio
class TestMainEndpoints:

    async def test_health_check_happy_case(self):
        """Happy Case: GET /health returns healthy status."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "fin-guardrail-api"}
        assert len(response.headers["X-Request-ID"]) == 32

    async def test_readiness_is_ready_in_mock_mode(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK_LLM", "true")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "checks": {"policy_corpus": True, "vision_provider": True},
        }

    async def test_readiness_fails_without_live_provider_key(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK_LLM", "false")
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["vision_provider"] is False

    async def test_metrics_expose_only_aggregate_runtime_data(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/metrics")

        assert response.status_code == 200
        assert set(response.json()) == {
            "counts",
            "request_latency_ms",
            "model_latency_ms",
        }

    async def test_document_preview_returns_normalized_image_without_caching(self):
        image_bytes = create_dummy_image_bytes()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/preview",
                files={"file": ("id.jpg", image_bytes, "image/jpeg")},
            )

        assert response.status_code == 200
        assert response.content == image_bytes
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"

    @patch("app.services.image_processor.render_single_page_pdf")
    async def test_document_preview_renders_pdf_as_png(self, mock_render_pdf):
        png_bytes = create_dummy_image_bytes(".png")
        mock_render_pdf.return_value = png_bytes

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/preview",
                files={
                    "file": (
                        "receipt.pdf",
                        b"%PDF-1.7\nsynthetic",
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 200
        assert response.content == png_bytes
        assert response.headers["content-type"] == "image/png"
        mock_render_pdf.assert_awaited_once()

    @patch("app.main.evaluate_thai_id_risk")
    @patch("app.main.extract_thai_id")
    async def test_blur_signal_with_successful_extraction_requires_review(
        self, mock_extract, mock_risk
    ):
        """Blur is supporting evidence and cannot independently reject an ID."""
        app.dependency_overrides[evaluate_image_quality_dependency] = (
            override_image_quality(blur_suspected=True)
        )
        try:
            mock_extract.return_value = load_mock_extraction(
                "mock_thai_id.json", ThaiIDExtraction
            )
            mock_risk.return_value = ([], 0.0)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/validate/thai-id",
                    files={
                        "file": ("id.jpg", create_dummy_image_bytes(), "image/jpeg")
                    },
                )

            payload = response.json()
            assert response.status_code == 200
            assert payload["status"] == "FLAGGED_FOR_REVIEW"
            assert payload["workflow"]["action"] == "HUMAN_REVIEW"
            assert payload["quality"]["disposition"] == "HUMAN_REVIEW"
            assert payload["quality"]["image"]["advisory_codes"] == ["POSSIBLE_BLUR"]
        finally:
            app.dependency_overrides.clear()

    @patch("app.main.extract_thai_id")
    async def test_validate_thai_id_unreadable_extraction_failed_case(
        self, mock_extract
    ):
        """Failed Case: Vision extractor returning None triggers unreadable document response."""
        mock_extract.return_value = None

        app.dependency_overrides[evaluate_image_quality_dependency] = (
            override_image_quality()
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/validate/thai-id",
                    files={
                        "file": ("id.jpg", create_dummy_image_bytes(), "image/jpeg")
                    },
                )

                assert response.status_code == 200
                payload = response.json()
                assert payload["status"] == "REJECTED"
                assert (
                    "UNREADABLE_DOCUMENT"
                    in payload["validation_flags"][0].split(":")[0]
                )
                assert payload["workflow"]["action"] == "REQUEST_RESUBMISSION"
                assert payload["quality"]["disposition"] == "REQUEST_RESUBMISSION"
        finally:
            # Clean up overrides after test run
            app.dependency_overrides.clear()

    @patch("app.main.evaluate_thai_id_risk")
    @patch("app.main.extract_thai_id")
    async def test_validate_thai_id_approved_happy_case(self, mock_extract, mock_risk):
        """Happy Case: Valid non-blurry ID clean validation returns APPROVED status."""

        app.dependency_overrides[evaluate_image_quality_dependency] = (
            override_image_quality()
        )
        try:
            mock_extract.return_value = load_mock_extraction(
                "mock_thai_id.json", ThaiIDExtraction
            )
            mock_risk.return_value = ([], 0.0)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/validate/thai-id",
                    files={
                        "file": ("id.jpg", create_dummy_image_bytes(), "image/jpeg")
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "APPROVED"
            assert payload["risk_score"] == 0.0
            assert payload["document_type"] == "thai_id"
            assert payload["workflow"]["action"] == "APPROVE"
            assert payload["workflow"]["human_review_required"] is False
            assert payload["quality"]["disposition"] == "CONTINUE"
        finally:
            # Clean up overrides after test run
            app.dependency_overrides.clear()

    @patch("app.main.evaluate_medical_claim_risk")
    @patch("app.main.extract_medical_receipt")
    async def test_validate_medical_receipt_flagged_for_review_edge_case(
        self, mock_extract, mock_risk
    ):
        """Edge Case: Risk score > 0.0 and < 0.7 routes status to FLAGGED_FOR_REVIEW."""

        app.dependency_overrides[evaluate_image_quality_dependency] = (
            override_image_quality()
        )
        try:
            mock_extract.return_value = load_mock_extraction(
                "mock_medical_receipt.json", MedicalReceiptExtraction
            )
            mock_risk.return_value = (["ARITHMETIC_MISMATCH"], 0.5)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/validate/medical-receipt",
                    files={
                        "file": (
                            "receipt.jpg",
                            create_dummy_image_bytes(),
                            "image/jpeg",
                        )
                    },
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "FLAGGED_FOR_REVIEW"
            assert payload["risk_score"] == 0.5
            assert "ARITHMETIC_MISMATCH" in payload["validation_flags"]
            assert payload["workflow"]["action"] == "HUMAN_REVIEW"
            assert payload["workflow"]["human_review_required"] is True
        finally:
            # Clean up overrides after test run
            app.dependency_overrides.clear()
