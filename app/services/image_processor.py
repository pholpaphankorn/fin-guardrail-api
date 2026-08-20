from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from fastapi import UploadFile, File, HTTPException, Depends

from app.schemas import ImageQualitySignals
from app.services.pdf_processor import render_single_page_pdf

DEFAULT_BLUR_THRESHOLD = 50.0
MIN_PROCESSED_DIMENSION = 320
MAX_IMAGE_DIMENSION = 1920
MAX_IMAGE_PIXELS = 25_000_000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
CONTENT_TYPE_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


@dataclass(frozen=True)
class ImageQualityAssessment:
    """Internal upload result with advisory-only image quality signals."""

    image_bytes: bytes
    width: int
    height: int
    focus_score: float
    blur_suspected: bool
    low_resolution_suspected: bool

    def public_signals(self) -> ImageQualitySignals:
        advisory_codes = []
        if self.blur_suspected:
            advisory_codes.append("POSSIBLE_BLUR")
        if self.low_resolution_suspected:
            advisory_codes.append("LOW_PROCESSED_RESOLUTION")
        return ImageQualitySignals(
            width=self.width,
            height=self.height,
            focus_score=round(self.focus_score, 3),
            blur_suspected=self.blur_suspected,
            low_resolution_suspected=self.low_resolution_suspected,
            advisory_codes=advisory_codes,
        )


def detect_image_content_type(file_bytes: bytes) -> str | None:
    """Identify supported document formats from their binary signatures."""
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def normalize_image_bytes(file_bytes: bytes, output_extension: str) -> bytes:
    """Validate, safely resize, and encode image bytes for vision extraction."""
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(
            status_code=400, detail="Corrupted or unreadable image file."
        )
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Decoded image dimensions exceed the processing safety limit.",
        )

    resized_image, was_resized = resize_image_if_needed(image, MAX_IMAGE_DIMENSION)
    if not was_resized:
        return file_bytes

    encode_extension = ".jpg" if output_extension in {".jpg", ".jpeg"} else ".png"
    options = [int(cv2.IMWRITE_JPEG_QUALITY), 90] if encode_extension == ".jpg" else []
    success, encoded_img = cv2.imencode(encode_extension, resized_image, options)
    if not success:
        raise HTTPException(
            status_code=400, detail="Could not normalize document image."
        )
    return encoded_img.tobytes()


def resize_image_if_needed(
    image: np.ndarray, max_dim: int = MAX_IMAGE_DIMENSION
) -> tuple[np.ndarray, bool]:
    """Resizes an image array if its maximum dimension exceeds max_dim while preserving aspect ratio."""
    height, width = image.shape[:2]
    max_current_dim = max(height, width)

    if max_current_dim <= max_dim:
        return image, False

    scale = max_dim / float(max_current_dim)
    new_width = int(width * scale)
    new_height = int(height * scale)

    resized_image = cv2.resize(
        image, (new_width, new_height), interpolation=cv2.INTER_AREA
    )
    return resized_image, True


def evaluate_image_blur(
    image_gray: np.ndarray,
    threshold: float = DEFAULT_BLUR_THRESHOLD,
    grid_size: int = 4,
) -> tuple[bool, float]:
    """Evaluates sharpness on the top 30% highest-variance grid patches.

    Splits the image into a grid (e.g. 4x4) and calculates Laplacian variance per patch.
    Averages only the top sharpest patches where high-contrast text lives, automatically
    ignoring smooth background surfaces (tables, desks, whitespace) regardless of card framing.
    """
    h, w = image_gray.shape[:2]
    patch_h, patch_w = h // grid_size, w // grid_size
    scores = []

    for row in range(grid_size):
        for col in range(grid_size):
            y1, y2 = row * patch_h, (row + 1) * patch_h
            x1, x2 = col * patch_w, (col + 1) * patch_w
            patch = image_gray[y1:y2, x1:x2]

            if patch.size > 0:
                scores.append(float(cv2.Laplacian(patch, cv2.CV_64F).var()))

    if not scores:
        return True, 0.0

    # Sort descending and average top 30% patches (where card text/edges are concentrated)
    scores.sort(reverse=True)
    top_k = max(1, int(len(scores) * 0.30))
    blur_score = float(np.mean(scores[:top_k]))

    is_blurry = blur_score < threshold
    return is_blurry, blur_score


# --- FastAPI Dependencies ---


async def get_resized_image_bytes(file: UploadFile = File(...)) -> bytes:
    """
    Dependency 1: Format validation + Smart Resize.
    Reads an image or single-page PDF, validates its format, renders PDFs,
    downscales if needed, and returns normalized image bytes.
    """
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in CONTENT_TYPE_BY_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Upload a PNG, JPEG, or single-page PDF.",
        )
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Upload a PNG, JPEG, or PDF.",
        )
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    detected_type = detect_image_content_type(file_bytes)
    expected_type = CONTENT_TYPE_BY_EXTENSION[extension]
    declared_type = file.content_type
    if detected_type is not None and (
        detected_type != expected_type
        or (declared_type is not None and detected_type != declared_type)
    ):
        raise HTTPException(
            status_code=415,
            detail="File content does not match its filename or declared media type.",
        )
    if expected_type == "application/pdf" and detected_type is None:
        raise HTTPException(
            status_code=415,
            detail="File content does not match its filename or declared media type.",
        )

    if expected_type == "application/pdf":
        rendered_bytes = await render_single_page_pdf(file_bytes)
        return normalize_image_bytes(rendered_bytes, ".png")

    return normalize_image_bytes(file_bytes, extension)


async def evaluate_image_quality_dependency(
    resized_bytes: bytes = Depends(get_resized_image_bytes),
) -> ImageQualityAssessment:
    """Collect advisory image signals without making a document decision.

    Blur and dimensions are weak proxies for text legibility. The endpoint combines
    these signals with structured extraction completeness and confidence before it
    chooses straight-through processing, human review, or resubmission.
    """
    nparr = np.frombuffer(resized_bytes, np.uint8)
    image_gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if image_gray is None:
        return ImageQualityAssessment(
            image_bytes=resized_bytes,
            width=0,
            height=0,
            focus_score=0.0,
            blur_suspected=True,
            low_resolution_suspected=True,
        )

    height, width = image_gray.shape[:2]
    blur_suspected, focus_score = evaluate_image_blur(image_gray)
    return ImageQualityAssessment(
        image_bytes=resized_bytes,
        width=width,
        height=height,
        focus_score=focus_score,
        blur_suspected=blur_suspected,
        low_resolution_suspected=min(width, height) < MIN_PROCESSED_DIMENSION,
    )
