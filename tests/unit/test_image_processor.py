import io
import os
import cv2
import numpy as np
import pytest
from fastapi import HTTPException, UploadFile

from app.services.image_processor import (
    resize_image_if_needed,
    evaluate_image_blur,
    get_resized_image_bytes,
    evaluate_blur_dependency,
    MAX_IMAGE_DIMENSION,
    DEFAULT_BLUR_THRESHOLD,
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

    def test_resize_image_if_needed_no_resize(self):
        """Happy case: Small image stays untouched."""
        img = np.zeros((500, 800, 3), dtype=np.uint8)
        resized, was_resized = resize_image_if_needed(
            img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is False
        assert resized.shape == (500, 800, 3)

    def test_resize_image_if_needed_oversized_landscape(self):
        """Happy case: Resizes large width (>1920px) while maintaining aspect ratio."""
        img = np.zeros((2000, 4000, 3), dtype=np.uint8)  # 2:1 ratio
        resized, was_resized = resize_image_if_needed(
            img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is True
        assert max(resized.shape[:2]) == MAX_IMAGE_DIMENSION
        assert resized.shape[1] == MAX_IMAGE_DIMENSION  # Width scaled to 1920
        assert resized.shape[0] == 960  # Height scaled to 960

    def test_resize_image_if_needed_oversized_portrait(self):
        """Happy case: Resizes large height (>1920px) while maintaining aspect ratio."""
        img = np.zeros((3000, 1500, 3), dtype=np.uint8)  # 2:1 ratio
        resized, was_resized = resize_image_if_needed(
            img, max_dim=MAX_IMAGE_DIMENSION)

        assert was_resized is True
        assert resized.shape[0] == MAX_IMAGE_DIMENSION  # Height scaled to 1920
        assert resized.shape[1] == 960  # Width scaled to 960

    def test_resize_image_if_needed_exact_threshold_edge_case(self):
        """Edge case: Image exact max dimension equal to threshold."""
        img = np.zeros((1080, MAX_IMAGE_DIMENSION, 3), dtype=np.uint8)
        resized, was_resized = resize_image_if_needed(
            img, max_dim=MAX_IMAGE_DIMENSION)

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
        upload_file = create_mock_upload_file(
            large_bytes, "large_receipt.jpeg")

        processed_bytes = await get_resized_image_bytes(upload_file)

        # Decode resulting bytes to check dimensions
        decoded = cv2.imdecode(
            np.frombuffer(processed_bytes, np.uint8), cv2.IMREAD_COLOR
        )
        assert max(decoded.shape[:2]) == MAX_IMAGE_DIMENSION

    async def test_get_resized_image_bytes_invalid_extension_failure(self):
        """Failure case: Invalid file extension triggers HTTP 400."""
        raw_bytes = create_synthetic_image_bytes(800, 600)
        upload_file = create_mock_upload_file(raw_bytes, "document.pdf")

        with pytest.raises(HTTPException) as exc_info:
            await get_resized_image_bytes(upload_file)

        assert exc_info.value.status_code == 400
        assert "Invalid file format" in exc_info.value.detail

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

    async def test_evaluate_blur_dependency_sharp_image(self):
        """Happy case: Sharp image evaluates to is_blurry = False."""
        sharp_bytes = create_synthetic_image_bytes(
            1000, 800, add_text=True, blur_ksize=0
        )

        out_bytes, is_blurry, blur_score = await evaluate_blur_dependency(
            resized_bytes=sharp_bytes
        )

        assert out_bytes == sharp_bytes
        assert is_blurry is False
        assert blur_score >= DEFAULT_BLUR_THRESHOLD

    async def test_evaluate_blur_dependency_blurry_image(self):
        """Failure / Quality case: Heavy motion/Gaussian blur evaluates to is_blurry = True."""
        blurry_bytes = create_synthetic_image_bytes(
            1000, 800, add_text=True, blur_ksize=41
        )

        out_bytes, is_blurry, blur_score = await evaluate_blur_dependency(
            resized_bytes=blurry_bytes
        )

        assert out_bytes == blurry_bytes
        assert is_blurry is True
        assert blur_score < DEFAULT_BLUR_THRESHOLD

    async def test_evaluate_blur_dependency_corrupted_input_fallback(self):
        """Edge case: Unparseable byte stream falls back to blurry = True and 0.0 score safely."""
        bad_bytes = b"random_corrupt_data"

        out_bytes, is_blurry, blur_score = await evaluate_blur_dependency(
            resized_bytes=bad_bytes
        )

        assert out_bytes == bad_bytes
        assert is_blurry is True
        assert blur_score == 0.0


@pytest.mark.asyncio
class TestRealDocumentPipeline:

    async def test_real_thai_id_card_1_blur_pipeline(self):
        """Tests the exact FastAPI image processing pipeline for thai_id_card_1.jpg:

        1. UploadFile ingestion
        2. Image resizing (get_resized_image_bytes)
        3. Blur assessment (evaluate_blur_dependency)
        """
        image_path = os.path.join(
            "data", "mock_docs", "thai_id", "thai_id_card_1.jpg")

        if not os.path.exists(image_path):
            pytest.skip(f"Real test image missing at: {image_path}")

        # 1. Read real file bytes from disk
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        upload_file = create_mock_upload_file(file_bytes, "thai_id_card_1.jpg")

        # 2. Pass through pipeline step 1: Resizing
        resized_bytes = await get_resized_image_bytes(upload_file)

        # 3. Pass through pipeline step 2: Blur Dependency
        out_bytes, is_blurry, blur_score = await evaluate_blur_dependency(
            resized_bytes=resized_bytes
        )

        # Print debug diagnostic metrics
        print(f"\n[Real Pipeline Test] {image_path}")
        print(f" -> Raw Size: {len(file_bytes)} bytes")
        print(f" -> Resized Size: {len(resized_bytes)} bytes")
        print(f" -> Calculated Blur Score: {blur_score:.2f}")
        print(f" -> Threshold: {DEFAULT_BLUR_THRESHOLD}")
        print(f" -> Is Blurry Flag: {is_blurry}")

        # Assert expected pipeline behavior
        assert (
            is_blurry is False
        ), f"Real ID card flagged as blurry in pipeline! Score: {blur_score:.2f} (Threshold: {DEFAULT_BLUR_THRESHOLD})"
