import cv2
import numpy as np
from fastapi import UploadFile, File, HTTPException, Depends

DEFAULT_BLUR_THRESHOLD = 100.0
MAX_IMAGE_DIMENSION = 1920


def resize_image_if_needed(
    image: np.ndarray, 
    max_dim: int = MAX_IMAGE_DIMENSION
) -> tuple[np.ndarray, bool]:
    """Resizes an image array if its maximum dimension exceeds max_dim while preserving aspect ratio."""
    height, width = image.shape[:2]
    max_current_dim = max(height, width)

    if max_current_dim <= max_dim:
        return image, False

    scale = max_dim / float(max_current_dim)
    new_width = int(width * scale)
    new_height = int(height * scale)

    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized_image, True


def evaluate_image_blur(image_gray: np.ndarray, threshold: float = DEFAULT_BLUR_THRESHOLD) -> tuple[bool, float]:
    """Evaluates image sharpness using the Laplacian Variance method on a grayscale image array."""
    blur_score = float(cv2.Laplacian(image_gray, cv2.CV_64F).var())
    is_blurry = blur_score < threshold
    return is_blurry, blur_score


# --- FastAPI Dependencies ---

async def get_resized_image_bytes(file: UploadFile = File(...)) -> bytes:
    """
    Dependency 1: Format validation + Smart Resize.
    Reads upload stream, validates file extension, downscales if > 1920px,
    and returns optimized image bytes.
    """
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Upload an image file (.png, .jpg, .jpeg).",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Corrupted or unreadable image file.")

    resized_image, was_resized = resize_image_if_needed(image, MAX_IMAGE_DIMENSION)

    if was_resized:
        ext = ".jpg" if file.filename.lower().endswith((".jpg", ".jpeg")) else ".png"
        success, encoded_img = cv2.imencode(ext, resized_image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if success:
            return encoded_img.tobytes()

    return file_bytes


async def evaluate_blur_dependency(
    resized_bytes: bytes = Depends(get_resized_image_bytes)
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