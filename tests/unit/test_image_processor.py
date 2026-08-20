import io
import os
import cv2
import numpy as np
import pytest
from fastapi import HTTPException, UploadFile

from app.services.image_processor import (
    resize_image_if_needed,
    detect_image_content_type,
    evaluate_image_blur,
    get_resized_image_bytes,
    evaluate_image_quality_dependency,
    MAX_IMAGE_DIMENSION,
    DEFAULT_BLUR_THRESHOLD,
    MIN_PROCESSED_DIMENSION,
    MAX_UPLOAD_BYTES,
)

# --- Helper Functions for Generating Synthetic Image Streams ---


def create_synthetic_image_bytes(
    width: int,
    height: int,
    add_text: bool = True,
    blur_ksize: int = 0,
    ext: str = ".jpg",
) -> bytes:
    """Generates an in-memory image byte stream with optional text and blur."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img.fill(240)  # Light gray background

    if add_text:
        # High-contrast sharp patterns give high Laplacian variance
        cv2.putText(
            img,
            "FIN-GUARDRAIL TEST ID",
            (50, min(height - 20, 100)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 0),
            3,
        )
        cv2.rectangle(
            img,
            (20, 20),
            (min(width - 20, 400), min(height - 20, 300)),
            (0, 100, 200),
            2,
        )

    if blur_ksize > 0:
        # Gaussian blur softens edges, dropping variance
        img = cv2.GaussianBlur(img, (blur_ksize, blur_ksize), 0)

    success, encoded = cv2.imencode(ext, img)
    return encoded.tobytes()


def create_mock_upload_file(file_bytes: bytes, filename: str) -> UploadFile:
    """Creates a FastAPI UploadFile wrapper over memory bytes."""
    return UploadFile(filename=filename, file=io.BytesIO(file_bytes))


# --- Unit Tests: Pure Helper Functions ---


class TestPureImageProcessing:

    def test_detect_image_content_type_uses_binary_signature(self):
        png_bytes = create_synthetic_image_bytes(100, 100, ext=".png")
        jpeg_bytes = create_synthetic_image_bytes(100, 100, ext=".jpg")

        assert detect_image_content_type(png_bytes) == "image/png"
        assert detect_image_content_type(jpeg_bytes) == "image/jpeg"
        assert detect_image_content_type(b"%PDF-1.7\n") == "application/pdf"
        assert detect_image_content_type(b"not an image") is None

    def test_resize_image_if_needed_no_resize(self):
        """Happy case: Small image stays untouched."""
        img = np.zeros((500, 800, 3), dtype=np.uint8)
        resized, was_resized = resize_image_if_needed(img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is False
        assert resized.shape == (500, 800, 3)

    def test_resize_image_if_needed_oversized_landscape(self):
        """Happy case: Resizes large width (>1920px) while maintaining aspect ratio."""
        img = np.zeros((2000, 4000, 3), dtype=np.uint8)  # 2:1 ratio
        resized, was_resized = resize_image_if_needed(img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is True
        assert max(resized.shape[:2]) == MAX_IMAGE_DIMENSION
        assert resized.shape[1] == MAX_IMAGE_DIMENSION  # Width scaled to 1920
        assert resized.shape[0] == 960  # Height scaled to 960

    def test_resize_image_if_needed_oversized_portrait(self):
        """Happy case: Resizes large height (>1920px) while maintaining aspect ratio."""
        img = np.zeros((3000, 1500, 3), dtype=np.uint8)  # 2:1 ratio
        resized, was_resized = resize_image_if_needed(img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is True
        assert resized.shape[0] == MAX_IMAGE_DIMENSION  # Height scaled to 1920
        assert resized.shape[1] == 960  # Width scaled to 960

    def test_resize_image_if_needed_exact_threshold_edge_case(self):
        """Edge case: Image exact max dimension equal to threshold."""
        img = np.zeros((1080, MAX_IMAGE_DIMENSION, 3), dtype=np.uint8)
        resized, was_resized = resize_image_if_needed(img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is False
        assert resized.shape == (1080, MAX_IMAGE_DIMENSION, 3)

    def test_evaluate_image_blur_sharp_vs_blurry(self):
        """Happy & Failure cases for blur calculation."""
        sharp_bytes = create_synthetic_image_bytes(
            800, 600, add_text=True, blur_ksize=0
        )
        blurry_bytes = create_synthetic_image_bytes(
            800, 600, add_text=True, blur_ksize=35
        )

        sharp_gray = cv2.imdecode(
            np.frombuffer(sharp_bytes, np.uint8), cv2.IMREAD_GRAYSCALE
        )
        blurry_gray = cv2.imdecode(
            np.frombuffer(blurry_bytes, np.uint8), cv2.IMREAD_GRAYSCALE
        )

        is_blurry_sharp, sharp_score = evaluate_image_blur(
            sharp_gray, threshold=DEFAULT_BLUR_THRESHOLD
        )
        is_blurry_blur, blur_score = evaluate_image_blur(
            blurry_gray, threshold=DEFAULT_BLUR_THRESHOLD
        )

        assert is_blurry_sharp is False
        assert sharp_score >= DEFAULT_BLUR_THRESHOLD

        assert is_blurry_blur is True
        assert blur_score < DEFAULT_BLUR_THRESHOLD


# --- Async Integration Tests: FastAPI Dependencies ---


@pytest.mark.asyncio
class TestFastAPIDependencies:

    async def test_get_resized_image_bytes_happy_case(self):
        """Happy case: Valid small image passes format check and remains untouched."""
        raw_bytes = create_synthetic_image_bytes(800, 600)
        upload_file = create_mock_upload_file(raw_bytes, "thai_id.jpg")

        processed_bytes = await get_resized_image_bytes(upload_file)
        assert len(processed_bytes) > 0

    async def test_get_resized_image_bytes_resizes_oversized_file(self):
        """Happy case: Large image file is successfully resized down."""
        large_bytes = create_synthetic_image_bytes(3000, 2000, ext=".jpg")
        upload_file = create_mock_upload_file(large_bytes, "large_receipt.jpeg")

        processed_bytes = await get_resized_image_bytes(upload_file)

        # Decode resulting bytes to check dimensions
        decoded = cv2.imdecode(
            np.frombuffer(processed_bytes, np.uint8), cv2.IMREAD_COLOR
        )
        assert max(decoded.shape[:2]) == MAX_IMAGE_DIMENSION

    async def test_get_resized_image_bytes_invalid_extension_failure(self):
        """Failure case: Invalid file extension triggers HTTP 400."""
        raw_bytes = create_synthetic_image_bytes(800, 600)
        upload_file = create_mock_upload_file(raw_bytes, "document.txt")

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 400
        assert "Invalid file format" in exc_info.value.detail

    async def test_get_resized_image_bytes_renders_single_page_pdf(self, monkeypatch):
        rendered_bytes = create_synthetic_image_bytes(800, 1200, ext=".png")

        async def render_pdf(pdf_bytes: bytes) -> bytes:
            assert pdf_bytes.startswith(b"%PDF-")
            return rendered_bytes

        monkeypatch.setattr(
            "app.services.image_processor.render_single_page_pdf", render_pdf
        )
        upload_file = UploadFile(
            filename="receipt.pdf",
            file=io.BytesIO(b"%PDF-1.7\nsynthetic"),
            headers={"content-type": "application/pdf"},
        )

        processed_bytes = await get_resized_image_bytes(upload_file)

        assert processed_bytes == rendered_bytes

    async def test_get_resized_image_bytes_rejects_invalid_pdf_signature(self):
        upload_file = UploadFile(
            filename="receipt.pdf",
            file=io.BytesIO(b"not-a-pdf"),
            headers={"content-type": "application/pdf"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 415
        assert "does not match" in exc_info.value.detail

    async def test_get_resized_image_bytes_empty_file_failure(self):
        """Failure case: Empty byte stream triggers HTTP 400."""
        upload_file = create_mock_upload_file(b"", "empty.jpg")

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 400
        assert "file is empty" in exc_info.value.detail

    async def test_get_resized_image_bytes_corrupted_image_failure(self):
        """Failure case: Non-image corrupt binary triggers HTTP 400."""
        corrupt_bytes = b"THIS_IS_NOT_AN_IMAGE_PAYLOAD_12345"
        upload_file = create_mock_upload_file(corrupt_bytes, "corrupt.png")

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 400
        assert "Corrupted or unreadable" in exc_info.value.detail

    async def test_get_resized_image_bytes_rejects_oversized_upload(self):
        upload_file = UploadFile(
            filename="oversized.jpg",
            file=io.BytesIO(b"x"),
            size=MAX_UPLOAD_BYTES + 1,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 413
        assert "10 MB" in exc_info.value.detail

    async def test_get_resized_image_bytes_rejects_mismatched_media_type(self):
        raw_bytes = create_synthetic_image_bytes(800, 600)
        upload_file = UploadFile(
            filename="document.jpg",
            file=io.BytesIO(raw_bytes),
            headers={"content-type": "text/plain"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 415

    async def test_get_resized_image_bytes_rejects_mismatched_binary_signature(self):
        png_bytes = create_synthetic_image_bytes(800, 600, ext=".png")
        upload_file = UploadFile(
            filename="document.png",
            file=io.BytesIO(png_bytes),
            headers={"content-type": "image/jpeg"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 415
        assert "does not match" in exc_info.value.detail

    async def test_image_quality_reports_sharp_image_without_advisory(self):
        sharp_bytes = create_synthetic_image_bytes(
            1000, 800, add_text=True, blur_ksize=0
        )

        report = await evaluate_image_quality_dependency(resized_bytes=sharp_bytes)

        assert report.image_bytes == sharp_bytes
        assert report.blur_suspected is False
        assert report.focus_score >= DEFAULT_BLUR_THRESHOLD
        assert report.public_signals().advisory_codes == []

    async def test_image_quality_reports_blur_as_advisory(self):
        blurry_bytes = create_synthetic_image_bytes(
            1000, 800, add_text=True, blur_ksize=41
        )

        report = await evaluate_image_quality_dependency(resized_bytes=blurry_bytes)

        assert report.image_bytes == blurry_bytes
        assert report.blur_suspected is True
        assert report.focus_score < DEFAULT_BLUR_THRESHOLD
        assert report.public_signals().advisory_codes == ["POSSIBLE_BLUR"]

    async def test_image_quality_corrupted_input_falls_back_to_advisories(self):
        bad_bytes = b"random_corrupt_data"

        report = await evaluate_image_quality_dependency(resized_bytes=bad_bytes)

        assert report.image_bytes == bad_bytes
        assert report.blur_suspected is True
        assert report.low_resolution_suspected is True
        assert report.focus_score == 0.0

    async def test_image_quality_reports_small_processed_dimensions(self):
        small_bytes = create_synthetic_image_bytes(
            MIN_PROCESSED_DIMENSION - 1,
            MIN_PROCESSED_DIMENSION - 1,
            add_text=True,
        )

        report = await evaluate_image_quality_dependency(resized_bytes=small_bytes)

        assert report.low_resolution_suspected is True
        assert "LOW_PROCESSED_RESOLUTION" in report.public_signals().advisory_codes


@pytest.mark.asyncio
class TestSyntheticDocumentPipeline:

    async def test_synthetic_thai_id_blur_pipeline(self):
        """Tests the exact FastAPI image pipeline with a synthetic KYC fixture:

        1. UploadFile ingestion
        2. Image resizing (get_resized_image_bytes)
        3. Advisory image quality assessment
        """
        image_path = os.path.join(
            "data", "mock_docs", "thai_id", "synthetic_thai_id.png"
        )

        if not os.path.exists(image_path):
            pytest.skip(f"Synthetic test image missing at: {image_path}")

        # 1. Read real file bytes from disk
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        upload_file = create_mock_upload_file(file_bytes, "synthetic_thai_id.png")

        # 2. Pass through pipeline step 1: Resizing
        resized_bytes = await get_resized_image_bytes(upload_file)

        # 3. Pass through pipeline step 2: Advisory quality assessment
        report = await evaluate_image_quality_dependency(resized_bytes=resized_bytes)

        # Print debug diagnostic metrics
        print(f"\n[Synthetic Pipeline Test] {image_path}")
        print(f" -> Raw Size: {len(file_bytes)} bytes")
        print(f" -> Resized Size: {len(resized_bytes)} bytes")
        print(f" -> Calculated Blur Score: {report.focus_score:.2f}")
        print(f" -> Threshold: {DEFAULT_BLUR_THRESHOLD}")
        print(f" -> Is Blurry Flag: {report.blur_suspected}")

        # Assert expected pipeline behavior
        assert (
            report.blur_suspected is False
        ), f"Synthetic ID fixture raised a blur advisory! Score: {report.focus_score:.2f} (Threshold: {DEFAULT_BLUR_THRESHOLD})"

    async def test_synthetic_medical_receipt_is_readable(self):
        """Verifies that the synthetic receipt is not rejected as blurry."""
        image_path = os.path.join(
            "data",
            "mock_docs",
            "thai_medical_receipt",
            "synthetic_medical_receipt.png",
        )

        if not os.path.exists(image_path):
            pytest.skip(f"Synthetic test image missing at: {image_path}")

        # 1. Read real file bytes from disk
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        upload_file = create_mock_upload_file(
            file_bytes, "synthetic_medical_receipt.png"
        )

        # 2. Pass through pipeline (Resize -> advisory quality signals)
        resized_bytes = await get_resized_image_bytes(upload_file)
        report = await evaluate_image_quality_dependency(resized_bytes=resized_bytes)

        # Print debug diagnostics
        print(f"\n[Synthetic Pipeline Test] {image_path}")
        print(f" -> Raw Size: {len(file_bytes)} bytes")
        print(f" -> Resized Size: {len(resized_bytes)} bytes")
        print(f" -> Calculated Blur Score: {report.focus_score:.2f}")
        print(f" -> Threshold: {DEFAULT_BLUR_THRESHOLD}")
        print(f" -> Is Blurry Flag: {report.blur_suspected}")

        # This fixture contains crisp text and edges; generated blur cases cover true blur.
        assert (
            report.blur_suspected is False
        ), f"Expected no blur advisory, but got focus_score={report.focus_score:.2f} (threshold={DEFAULT_BLUR_THRESHOLD})"
