from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "fin-guardrail-api"}


def test_validate_thai_id_invalid_extension():
    file_bytes = BytesIO(b"dummy pdf content")
    files = {"file": ("test.pdf", file_bytes, "application/pdf")}

    response = client.post("/api/v1/validate/thai-id", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


def test_validate_medical_receipt_invalid_extension():
    file_bytes = BytesIO(b"dummy pdf content")
    files = {"file": ("test.pdf", file_bytes, "application/pdf")}

    response = client.post("/api/v1/validate/medical-receipt", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]
