import os
import glob
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_E2E", "false").lower() != "true",
    reason="Set RUN_LIVE_E2E=true to authorize credential-dependent model calls.",
)

# Path to your test images folder
MOCK_DOCS_DIR = os.path.join("data", "mock_docs", "thai_id")


def get_thai_id_image_paths():
    """Helper function to discover all image files in the mock_docs directory."""
    if not os.path.exists(MOCK_DOCS_DIR):
        return []

    # Collect all jpg, jpeg, and png images
    extensions = ("*.jpg", "*.jpeg", "*.png")
    image_paths = []
    for ext in extensions:
        image_paths.extend(glob.glob(os.path.join(MOCK_DOCS_DIR, ext)))

    return sorted(image_paths)


# Get file list at test collection time
IMAGE_PATHS = get_thai_id_image_paths()


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "image_path",
    IMAGE_PATHS,
    ids=[os.path.basename(p) for p in IMAGE_PATHS],  # Shows image name in pytest output
)
async def test_full_thai_id_validation_pipeline_e2e(image_path: str, monkeypatch):
    """E2E Test: Uploads each sample ID photo in data/mock_docs/thai_id through the API pipeline.

    Flow: HTTP Request -> Image Pre-processing (Blur) -> Live Vision LLM -> Risk Validator -> HTTP JSON Response
    """
    if not IMAGE_PATHS:
        pytest.skip(f"No test images found in {MOCK_DOCS_DIR}")

    monkeypatch.setenv("USE_MOCK_LLM", "false")

    # 1. Load image file
    with open(image_path, "rb") as image_file:
        file_bytes = image_file.read()

    file_name = os.path.basename(image_path)
    media_type = "image/png" if file_name.lower().endswith(".png") else "image/jpeg"

    # 2. Issue multipart POST request to FastAPI endpoint
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/validate/thai-id",
            files={"file": (file_name, file_bytes, media_type)},
        )

    # 3. Assert HTTP Layer Contract
    assert response.status_code == 200
    payload = response.json()

    # 4. Assert E2E Payload Structure
    assert payload["document_type"] == "thai_id"
    assert payload["status"] in ["APPROVED", "FLAGGED_FOR_REVIEW", "REJECTED"]
    assert "risk_score" in payload
    assert isinstance(payload["risk_score"], float)
    assert "extracted_data" in payload
    assert "validation_flags" in payload

    # Print summary output for terminal inspection
    print(
        f"\n✅ [{file_name}] Status: {payload['status']} | Risk Score: {payload['risk_score']}"
    )
