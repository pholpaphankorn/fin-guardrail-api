import json
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.main import app
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction


@pytest.fixture
def anyio_backend():
    return "asyncio"


def create_dummy_image_bytes() -> bytes:
    """Returns minimalist valid JPEG bytes for router testing."""
    import cv2
    import numpy as np

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img.fill(200)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def load_mock_extraction(filename: str, schema):
    mock_path = Path("data/mock_jsons") / filename
    return schema.model_validate(json.loads(mock_path.read_text(encoding="utf-8")))


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

    @patch("app.main.evaluate_blur_dependency")
    async def test_validate_thai_id_blurry_rejection_failed_case(self, mock_blur_dep):
        """Failed / Rejection Case: Blurry image returned from dependency triggers HTTP 200 Business Rejection."""
        mock_blur_dep.return_value = (b"image_bytes", True, 45.0)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/validate/thai-id",
                files={"file": ("id.jpg", create_dummy_image_bytes(), "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "REJECTED"
        assert payload["risk_score"] == 1.0
        assert "BLURRY_IMAGE_DETECTED" in payload["validation_flags"][0]

    @patch("app.main.extract_thai_id")
    @patch("app.main.evaluate_blur_dependency")
    async def test_validate_thai_id_unreadable_extraction_failed_case(
        self, mock_blur_dep, mock_extract
    ):
        """Failed Case: Vision extractor returning None triggers unreadable document response."""
        mock_extract.return_value = None

        async def mock_blur_override():
            return (b"image_bytes", False, 150.0)

        from app.services.image_processor import evaluate_blur_dependency

        app.dependency_overrides[evaluate_blur_dependency] = mock_blur_override
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
        finally:
            # Clean up overrides after test run
            app.dependency_overrides.clear()

    @patch("app.main.evaluate_thai_id_risk")
    @patch("app.main.extract_thai_id")
    @patch("app.main.evaluate_blur_dependency")
    async def test_validate_thai_id_approved_happy_case(
        self, mock_blur_dep, mock_extract, mock_risk
    ):
        """Happy Case: Valid non-blurry ID clean validation returns APPROVED status."""

        async def mock_blur_override():
            return (b"image_bytes", False, 180.0)

        from app.services.image_processor import evaluate_blur_dependency

        app.dependency_overrides[evaluate_blur_dependency] = mock_blur_override
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
        finally:
            # Clean up overrides after test run
            app.dependency_overrides.clear()

    @patch("app.main.evaluate_medical_claim_risk")
    @patch("app.main.extract_medical_receipt")
    @patch("app.main.evaluate_blur_dependency")
    async def test_validate_medical_receipt_flagged_for_review_edge_case(
        self, mock_blur_dep, mock_extract, mock_risk
    ):
        """Edge Case: Risk score > 0.0 and < 0.7 routes status to FLAGGED_FOR_REVIEW."""

        async def mock_blur_override():
            return (b"image_bytes", False, 180.0)

        from app.services.image_processor import evaluate_blur_dependency

        app.dependency_overrides[evaluate_blur_dependency] = mock_blur_override
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
