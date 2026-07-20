from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "fin-guardrail-api"}


def test_validate_document_invalid_extension():
    file_bytes = BytesIO(b"dummy pdf content")
    files = {"file": ("test.pdf", file_bytes, "application/pdf")}

    response = client.post("/api/v1/validate-document?doc_type=thai_id", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


def test_validate_document_invalid_doc_type():
    file_bytes = BytesIO(b"dummy image content")
    files = {"file": ("test.png", file_bytes, "image/png")}

    response = client.post(
        "/api/v1/validate-document?doc_type=invalid_type", files=files
    )
    assert response.status_code in [400, 422]
