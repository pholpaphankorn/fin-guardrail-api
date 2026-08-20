import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import HTTPException

from app.services.pdf_processor import parse_pdf_page_count, render_single_page_pdf


def png_bytes() -> bytes:
    image = np.full((600, 400, 3), 240, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


def minimal_pdf_bytes() -> bytes:
    """Build a tiny synthetic one-page PDF without adding a test dependency."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 300] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 36 >>\nstream\nBT /F1 18 Tf 20 150 Td (TEST) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def test_parse_pdf_page_count():
    assert parse_pdf_page_count(b"Title: Example\nPages:          1\n") == 1
    assert parse_pdf_page_count(b"Title: Example\n") is None


@pytest.mark.asyncio
async def test_poppler_renders_synthetic_single_page_pdf_when_available():
    if not shutil.which("pdfinfo") or not shutil.which("pdftoppm"):
        pytest.skip("Poppler is not installed in this environment")

    result = await render_single_page_pdf(minimal_pdf_bytes())
    decoded = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)

    assert decoded is not None
    assert max(decoded.shape[:2]) == 1920


@pytest.mark.asyncio
async def test_render_single_page_pdf_returns_rendered_png(monkeypatch):
    rendered_bytes = png_bytes()

    async def run_command(*command: str, capture_stdout: bool = False):
        if command[0] == "pdfinfo":
            assert capture_stdout is True
            return 0, b"Pages:          1\n", b""
        Path(f"{command[-1]}.png").write_bytes(rendered_bytes)
        return 0, b"", b""

    monkeypatch.setattr("app.services.pdf_processor._run_pdf_command", run_command)

    result = await render_single_page_pdf(b"%PDF-1.7\nsynthetic")

    assert result == rendered_bytes


@pytest.mark.asyncio
async def test_render_single_page_pdf_rejects_multiple_pages(monkeypatch):
    async def run_command(*command: str, capture_stdout: bool = False):
        return 0, b"Pages:          2\n", b""

    monkeypatch.setattr("app.services.pdf_processor._run_pdf_command", run_command)

    with pytest.raises(HTTPException) as exc_info:
        await render_single_page_pdf(b"%PDF-1.7\nsynthetic")

    assert exc_info.value.status_code == 400
    assert "exactly one page" in exc_info.value.detail


@pytest.mark.asyncio
async def test_render_single_page_pdf_rejects_encrypted_pdf(monkeypatch):
    async def run_command(*command: str, capture_stdout: bool = False):
        return 1, b"", b"Command Line Error: Incorrect password"

    monkeypatch.setattr("app.services.pdf_processor._run_pdf_command", run_command)

    with pytest.raises(HTTPException) as exc_info:
        await render_single_page_pdf(b"%PDF-1.7\nsynthetic")

    assert exc_info.value.status_code == 400
    assert "Password-protected" in exc_info.value.detail
