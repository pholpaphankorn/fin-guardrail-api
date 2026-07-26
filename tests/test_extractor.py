import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import UploadFile, HTTPException
from app.services.extractor import (
    cleanup_raw_content,
    encode_file_to_base64,
    extract_thai_id,
    extract_medical_receipt,
)
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction

# =====================================================================
# 1. HELPER FUNCTION TESTS
# =====================================================================


def test_cleanup_raw_content_markdown_wrapper():
    """Verify markdown fences are correctly stripped."""
    wrapped_json = '```json\n{"key": "value"}\n```'
    assert cleanup_raw_content(wrapped_json) == '{"key": "value"}'


def test_cleanup_raw_content_plain_json():
    """Verify raw JSON passes through unchanged."""
    plain_json = '{"key": "value"}'
    assert cleanup_raw_content(plain_json) == '{"key": "value"}'


def test_encode_file_to_base64():
    """Verify bytes convert cleanly to a base64 string."""
    sample_bytes = b"hello world"
    encoded = encode_file_to_base64(sample_bytes)
    assert isinstance(encoded, str)
    assert encoded == "aGVsbG8gd29ybGQ="


# =====================================================================
# 2. EXTRACTOR FUNCTION TESTS (MOCKED)
# =====================================================================


@pytest.mark.asyncio
async def test_extract_thai_id_empty_file():
    """Verify HTTP 400 is raised when the uploaded file is empty."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"")  # Empty byte stream

    try:
        await extract_thai_id(mock_file)
        assert False, "Expected HTTPException but none was raised"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "The uploaded file is empty" in exc.detail


@pytest.mark.asyncio
@patch("app.services.extractor.os.environ.get")
@patch("app.services.extractor.ollama_client")
async def test_extract_thai_id_success(mock_ollama, mock_env):
    """Test live LLM branch for Thai ID extraction."""
    mock_env.side_effect = lambda key, default=None: (
        "false" if key == "USE_MOCK_LLM" else "fake_key"
    )

    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake image bytes")

    mock_response = MagicMock()
    mock_response.message.content = """```json
    {
        "id_number": "0000000000000",
        "first_name_en": "TEST",
        "last_name_en": "USER",
        "date_of_birth": "1990-01-01",
        "expiry_date": "2030-01-01"
    }
    ```"""
    mock_ollama.chat.return_value = mock_response

    result = await extract_thai_id(mock_file)

    assert isinstance(result, ThaiIDExtraction)
    assert result.id_number == "0000000000000"
    assert result.first_name_en == "TEST"
    mock_ollama.chat.assert_called_once()


@pytest.mark.asyncio
async def test_extract_medical_receipt_empty_file():
    """Verify HTTP 400 is raised when an empty file is passed to medical receipt extractor."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"")  # Empty byte stream

    try:
        await extract_medical_receipt(mock_file)
        assert False, "Expected HTTPException but none was raised"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "The uploaded file is empty" in exc.detail


@pytest.mark.asyncio
@patch("app.services.extractor.os.environ.get")
@patch("app.services.extractor.ollama_client")
async def test_extract_medical_receipt_success(mock_ollama, mock_env):
    """Test live LLM branch for Medical Receipt extraction."""
    mock_env.side_effect = lambda key, default=None: (
        "false" if key == "USE_MOCK_LLM" else "fake_key"
    )

    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake receipt image bytes")

    mock_response = MagicMock()
    mock_response.message.content = """```json
    {
        "hospital_name": "Example Health Test Clinic",
        "receipt_date": "2026-01-01",
        "items": [
            {"description": "Consultation", "cost": 800.0},
            {"description": "Medication", "cost": 150.0}
        ],
        "total_amount": 950.0
    }
    ```"""
    mock_ollama.chat.return_value = mock_response

    result = await extract_medical_receipt(mock_file)

    assert isinstance(result, MedicalReceiptExtraction)
    assert result.hospital_name == "Example Health Test Clinic"
    assert result.receipt_date == "2026-01-01"
    assert len(result.items) == 2
    assert result.items[0].description == "Consultation"
    assert result.items[0].cost == 800.0
    assert result.total_amount == 950.0
    mock_ollama.chat.assert_called_once()
