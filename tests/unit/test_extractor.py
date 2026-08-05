import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.extractor import (
    encode_file_to_base64,
    cleanup_raw_content,
    extract_thai_id,
    extract_medical_receipt,
    _call_vision_model,
)
from app.schemas import ThaiIDExtraction


class TestExtractorHelpers:

    def test_encode_file_to_base64(self):
        """Happy Case: Encodes raw bytes to base64 string."""
        raw_bytes = b"hello_world"
        encoded = encode_file_to_base64(raw_bytes)
        assert encoded == "aGVsbG9fd29ybGQ="

    def test_cleanup_raw_content_markdown_json(self):
        """Happy & Edge Case: Strips markdown code fences from JSON text."""
        assert cleanup_raw_content('```json\n{"key": "val"}\n```') == '{"key": "val"}'
        assert cleanup_raw_content('```\n{"key": "val"}\n```') == '{"key": "val"}'
        assert cleanup_raw_content('{"key": "val"}') == '{"key": "val"}'


@pytest.mark.asyncio
class TestVisionModelExtraction:

    async def test_call_vision_model_failed_case_empty_bytes(self):
        """Failed Case: Empty byte stream raises HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            await _call_vision_model(
                file_bytes=b"",
                prompt_instruction="Test",
                target_schema=ThaiIDExtraction,
                mock_file_path="dummy.json",
            )
        assert exc_info.value.status_code == 400

    @patch.dict("os.environ", {"USE_MOCK_LLM": "true"})
    async def test_extract_thai_id_happy_case_mock_mode(self, tmp_path):
        """Happy Case: Extract Thai ID using mock environment flag."""
        mock_data = {
            "id_number": "1234567890123",
            "first_name_en": "TEST",
            "last_name_en": "Dee",
            "date_of_birth": "1990-01-01",
            "expiry_date": "2028-01-01",
            "confidence_score": 0.95,
        }
        mock_file = tmp_path / "mock_id.json"
        mock_file.write_text(json.dumps(mock_data), encoding="utf-8")

        res = await _call_vision_model(
            file_bytes=b"valid_image_bytes",
            prompt_instruction="Prompt",
            target_schema=ThaiIDExtraction,
            mock_file_path=str(mock_file),
        )

        assert res.id_number == "1234567890123"
        assert res.first_name_en == "TEST"

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false"})
    @patch("app.services.extractor.ollama_client.chat")
    async def test_call_vision_model_retry_success(self, mock_chat):
        """Edge Case: Retries with correction prompt after Attempt 1 fails JSON parsing, then succeeds."""
        invalid_resp = MagicMock()
        invalid_resp.message.content = "{bad_json"

        valid_resp = MagicMock()
        valid_resp.message.content = json.dumps(
            {
                "id_number": "1100000000000",
                "first_name_en": "Jane",
                "last_name_en": "Doe",
                "date_of_birth": "1995-05-05",
                "expiry_date": "2030-05-05",
                "confidence_score": 0.9,
            }
        )

        # Attempt 1 returns invalid JSON, Attempt 2 returns valid schema
        mock_chat.side_effect = [invalid_resp, valid_resp]

        result = await extract_thai_id(file_bytes=b"dummy_bytes")

        assert result is not None
        assert result.id_number == "1100000000000"
        assert mock_chat.call_count == 2  # Verifies retry occurred

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false"})
    @patch("app.services.extractor.ollama_client.chat")
    async def test_call_vision_model_exhausted_retries_returns_none(self, mock_chat):
        """Failed Case: Returns None when both attempts fail schema parsing."""
        bad_resp = MagicMock()
        bad_resp.message.content = "Not JSON output"
        mock_chat.return_value = bad_resp

        result = await extract_thai_id(file_bytes=b"dummy_bytes")

        assert result is None
        assert mock_chat.call_count == 2
