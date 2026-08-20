import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ui_home_serves_document_validator():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Know what passes" in response.text
    assert "Thai ID card" in response.text
    assert "Medical receipt" in response.text
    assert "single-page PDF" in response.text
    assert "Policy evidence" in response.text
    assert "Tool audit trail" in response.text
    assert "Document quality evidence" in response.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ui_assets_and_sample_document_are_available():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        stylesheet = await client.get("/static/styles.css")
        script = await client.get("/static/app.js")
        sample = await client.get("/samples/thai_id/synthetic_thai_id.png")

    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert sample.status_code == 200
    assert sample.headers["content-type"] == "image/png"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ui_config_reports_demo_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/config")

    assert response.status_code == 200
    assert response.json() == {
        "demo_mode": True,
        "vision_provider": "Ollama Cloud",
        "max_upload_mb": 10,
        "prompt_versions": {
            "thai_id": "thai-id-extraction-v1.0.0",
            "medical_receipt": "medical-receipt-extraction-v1.0.0",
        },
    }
