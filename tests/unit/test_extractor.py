import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.extractor import (
    THAI_ID_PROMPT_VERSION,
    _create_ollama_client,
    encode_file_to_base64,
    cleanup_raw_content,
    extract_thai_id,
    extract_medical_receipt,
    _call_vision_model,
)
from app.schemas import ThaiIDExtraction


def valid_thai_id_payload(**overrides):
    """Return a complete confidence-wrapped extraction payload for tests."""
    payload = json.loads(
        Path("data/mock_jsons/mock_thai_id.json").read_text(encoding="utf-8")
    )
    payload.update(overrides)
    return payload


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
        mock_data = valid_thai_id_payload(
            id_number={"value": "1234567890121", "confidence": 0.99}
        )
        mock_file = tmp_path / "mock_id.json"
        mock_file.write_text(json.dumps(mock_data), encoding="utf-8")

        res = await _call_vision_model(
            file_bytes=b"valid_image_bytes",
            prompt_instruction="Prompt",
            target_schema=ThaiIDExtraction,
            mock_file_path=str(mock_file),
        )

        assert res.id_number.value == "1234567890121"
        assert res.first_name_en.value == "TEST"

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false", "OLLAMA_API_KEY": "test-key"})
    @patch("app.services.extractor._create_ollama_client")
    async def test_call_vision_model_retry_success(self, mock_create_client):
        """Edge Case: Retries with correction prompt after Attempt 1 fails JSON parsing, then succeeds."""
        invalid_resp = MagicMock()
        invalid_resp.message.content = "{bad_json"

        valid_resp = MagicMock()
        valid_resp.message.content = json.dumps(
            valid_thai_id_payload(
                id_number={"value": "1234567890121", "confidence": 0.99},
                first_name_en={"value": "Jane", "confidence": 0.96},
                last_name_en={"value": "Doe", "confidence": 0.96},
            )
        )

        # Attempt 1 returns invalid JSON, Attempt 2 returns valid schema
        mock_chat = mock_create_client.return_value.chat
        mock_chat.side_effect = [invalid_resp, valid_resp]

        result = await extract_thai_id(file_bytes=b"dummy_bytes")

        assert result is not None
        assert result.id_number.value == "1234567890121"
        assert mock_chat.call_count == 2  # Verifies retry occurred
        initial_prompt = mock_chat.call_args_list[0].kwargs["messages"][0]["content"]
        retry_prompt = mock_chat.call_args_list[1].kwargs["messages"][0]["content"]
        assert f"PROMPT_VERSION: {THAI_ID_PROMPT_VERSION}" in initial_prompt
        assert f"PROMPT_VERSION: {THAI_ID_PROMPT_VERSION}" in retry_prompt

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false", "OLLAMA_API_KEY": "test-key"})
    @patch("app.services.extractor._create_ollama_client")
    async def test_call_vision_model_exhausted_retries_returns_none(
        self, mock_create_client
    ):
        """Failed Case: Returns None when both attempts fail schema parsing."""
        bad_resp = MagicMock()
        bad_resp.message.content = "Not JSON output"
        mock_chat = mock_create_client.return_value.chat
        mock_chat.return_value = bad_resp

        result = await extract_thai_id(file_bytes=b"dummy_bytes")

        assert result is None
        assert mock_chat.call_count == 2

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false"}, clear=True)
    async def test_live_extraction_requires_provider_key(self):
        with pytest.raises(HTTPException) as exc_info:
            await extract_thai_id(file_bytes=b"dummy_bytes")

        assert exc_info.value.status_code == 503

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false", "OLLAMA_API_KEY": "test-key"})
    @patch("app.services.extractor.asyncio.to_thread")
    async def test_provider_timeout_returns_stable_gateway_timeout(self, mock_thread):
        mock_thread.side_effect = TimeoutError

        with pytest.raises(HTTPException) as exc_info:
            await extract_thai_id(file_bytes=b"dummy_bytes")

        assert exc_info.value.status_code == 504

    @patch.dict("os.environ", {"USE_MOCK_LLM": "false", "OLLAMA_API_KEY": "test-key"})
    @patch("app.services.extractor._create_ollama_client")
    async def test_provider_failure_does_not_leak_internal_error(
        self, mock_create_client
    ):
        mock_chat = mock_create_client.return_value.chat
        mock_chat.side_effect = RuntimeError("secret upstream host and token")

        with pytest.raises(HTTPException) as exc_info:
            await extract_thai_id(file_bytes=b"dummy_bytes")

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "Vision provider request failed."
        assert "secret" not in exc_info.value.detail


@pytest.mark.unit
@patch("app.services.extractor.Client")
def test_provider_client_uses_validated_host_and_secret(mock_client, monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_HOST", "https://vision.example.test")

    from app.config import get_settings

    _create_ollama_client(get_settings())

    mock_client.assert_called_once_with(
        host="https://vision.example.test",
        headers={"Authorization": "Bearer test-key"},
    )
