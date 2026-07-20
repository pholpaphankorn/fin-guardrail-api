import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import UploadFile, HTTPException
from app.services.extractor import (
    cleanup_raw_content,
    encode_file_to_base64,
    extract_document_data,
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
# 2. EXTRACT_DOCUMENT_DATA TESTS (MOCKED)
# =====================================================================


@pytest.mark.asyncio
async def test_extract_document_data_unsupported_doc_type():
    """Verify HTTP 400 is raised when an unsupported doc_type is passed."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"some bytes")

    with pytest.raises(HTTPException) as exc_info:
        await extract_document_data(mock_file, "unsupported_type")

    assert exc_info.value.status_code == 400
    assert "Unsupported document mapping" in exc_info.value.detail


@pytest.mark.asyncio
async def test_extract_document_data_empty_file():
    """Verify HTTP 400 is raised when the uploaded file is empty."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"")  # Empty byte stream

    with pytest.raises(HTTPException) as exc_info:
        await extract_document_data(mock_file, "thai_id")

    assert exc_info.value.status_code == 400
    assert "The uploaded file is empty" in exc_info.value.detail


@pytest.mark.asyncio
@patch("app.services.extractor.os.environ.get")
@patch("app.services.extractor.ollama_client")
async def test_extract_document_data_ollama_cloud_success(mock_ollama, mock_env):
    """
    Test live LLM branch by mocking USE_MOCK_LLM=false and mocking
    the response from ollama_client.chat.
    """
    # 1. Configure environment mocks (USE_MOCK_LLM=false)
    mock_env.side_effect = lambda key, default=None: (
        "false" if key == "USE_MOCK_LLM" else "fake_key"
    )

    # 2. Mock incoming upload file
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake image bytes")

    # 3. Mock Ollama client response structure
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

    # 4. Execute function
    result = await extract_document_data(mock_file, "thai_id")

    # 5. Assertions
    assert isinstance(result, ThaiIDExtraction)
    assert result.id_number == "0000000000000"
    assert result.first_name_en == "TEST"
    mock_ollama.chat.assert_called_once()  # Verify LLM client was actually called


@pytest.mark.asyncio
@patch("app.services.extractor.os.environ.get")
@patch("app.services.extractor.ollama_client")
async def test_extract_document_data_medical_receipt_success(mock_ollama, mock_env):
    """
    Test live LLM branch for medical receipts by mocking USE_MOCK_LLM=false
    and verifying deserialization into MedicalReceiptExtraction.
    """
    # 1. Configure environment mocks (USE_MOCK_LLM=false)
    mock_env.side_effect = lambda key, default=None: (
        "false" if key == "USE_MOCK_LLM" else "fake_key"
    )

    # 2. Mock incoming upload file
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake receipt image bytes")

    # 3. Mock Ollama client response structure with medical receipt JSON
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

    # 4. Execute function for medical_receipt
    result = await extract_document_data(mock_file, "medical_receipt")

    # 5. Assertions
    assert isinstance(result, MedicalReceiptExtraction)
    assert result.hospital_name == "Example Health Test Clinic"
    assert result.receipt_date == "2026-01-01"
    assert len(result.items) == 2
    assert result.items[0].description == "Consultation"
    assert result.items[0].cost == 800.0
    assert result.total_amount == 950.0
    mock_ollama.chat.assert_called_once()
