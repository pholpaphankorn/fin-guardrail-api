import cv2
import numpy as np
from fastapi import UploadFile, File, HTTPException, Depends

DEFAULT_BLUR_THRESHOLD = 50.0
MAX_IMAGE_DIMENSION = 1920
MAX_IMAGE_PIXELS = 25_000_000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


def detect_image_content_type(file_bytes: bytes) -> str | None:
    """Identify supported image formats from their binary signatures."""
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


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
    Reads upload stream, validates file extension, downscales if > 1920px,
    and returns optimized image bytes.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Upload an image file (.png, .jpg, .jpeg).",
        )
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Upload a JPEG or PNG image.",
        )
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    detected_type = detect_image_content_type(file_bytes)
    expected_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    declared_type = file.content_type
    if detected_type is not None and (
        detected_type != expected_type
        or (declared_type is not None and detected_type != declared_type)
    ):
        raise HTTPException(
            status_code=415,
            detail="Image content does not match its filename or declared media type.",
        )

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

    if was_resized:
        ext = ".jpg" if filename.lower().endswith((".jpg", ".jpeg")) else ".png"
        success, encoded_img = cv2.imencode(
            ext, resized_image, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        )
        if success:
            return encoded_img.tobytes()

    return file_bytes


async def evaluate_blur_dependency(
    resized_bytes: bytes = Depends(get_resized_image_bytes),
) -> tuple[bytes, bool, float]:
    """
    Dependency 2: Blur Check.
    Takes output from get_resized_image_bytes, converts to grayscale,
    and calculates focus score.
    """
    nparr = np.frombuffer(resized_bytes, np.uint8)
    image_gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    if image_gray is None:
        return resized_bytes, True, 0.0

    is_blurry, blur_score = evaluate_image_blur(image_gray)
    return resized_bytes, is_blurry, blur_score
