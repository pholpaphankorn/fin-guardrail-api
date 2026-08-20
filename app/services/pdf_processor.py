"""Bounded conversion of untrusted single-page PDFs into PNG images."""

import asyncio
import re
import tempfile
from pathlib import Path

from fastapi import HTTPException

PDF_RENDER_TIMEOUT_SECONDS = 10.0
MAX_RENDERED_PDF_BYTES = 25 * 1024 * 1024
PDF_RENDER_MAX_DIMENSION = 1920


async def _run_pdf_command(
    *command: str, capture_stdout: bool = False
) -> tuple[int, bytes, bytes]:
    """Run a Poppler command with a hard timeout and bounded caller surface."""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=(
                asyncio.subprocess.PIPE
                if capture_stdout
                else asyncio.subprocess.DEVNULL
            ),
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="PDF processing is unavailable on this server.",
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=PDF_RENDER_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise HTTPException(
            status_code=408,
            detail="PDF processing exceeded the allowed time.",
        ) from exc

    return process.returncode or 0, (stdout or b"")[-4096:], stderr[-4096:]


def parse_pdf_page_count(pdfinfo_output: bytes) -> int | None:
    """Read Poppler's stable page-count field from pdfinfo output."""
    match = re.search(rb"^Pages:\s+(\d+)\s*$", pdfinfo_output, re.MULTILINE)
    return int(match.group(1)) if match else None


def _pdf_error_detail(stderr: bytes) -> str:
    message = stderr.decode("utf-8", errors="ignore").lower()
    if "password" in message or "encrypted" in message:
        return "Password-protected or encrypted PDFs are not supported."
    return "Corrupted or unreadable PDF file."


async def render_single_page_pdf(pdf_bytes: bytes) -> bytes:
    """Validate and render exactly one PDF page to a bounded PNG image."""
    with tempfile.TemporaryDirectory(prefix="fin-guardrail-pdf-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "upload.pdf"
        output_prefix = temp_path / "page"
        output_path = temp_path / "page.png"
        input_path.write_bytes(pdf_bytes)

        info_code, stdout, stderr = await _run_pdf_command(
            "pdfinfo",
            str(input_path),
            capture_stdout=True,
        )
        if info_code != 0:
            raise HTTPException(status_code=400, detail=_pdf_error_detail(stderr))

        page_count = parse_pdf_page_count(stdout)
        if page_count is None:
            raise HTTPException(status_code=400, detail="Could not inspect PDF pages.")
        if page_count != 1:
            raise HTTPException(
                status_code=400,
                detail="PDF must contain exactly one page.",
            )

        return_code, _, render_stderr = await _run_pdf_command(
            "pdftoppm",
            "-f",
            "1",
            "-l",
            "1",
            "-singlefile",
            "-png",
            "-scale-to",
            str(PDF_RENDER_MAX_DIMENSION),
            str(input_path),
            str(output_prefix),
        )
        if return_code != 0 or not output_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=_pdf_error_detail(render_stderr),
            )
        if output_path.stat().st_size > MAX_RENDERED_PDF_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Rendered PDF page exceeds the processing safety limit.",
            )

        return output_path.read_bytes()
