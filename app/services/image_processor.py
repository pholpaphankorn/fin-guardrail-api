import cv2
import numpy as np
from fastapi import UploadFile, File, HTTPException

DEFAULT_BLUR_THRESHOLD = 100.0


def evaluate_image_blur(file_bytes: bytes, threshold: float = DEFAULT_BLUR_THRESHOLD) -> tuple[bool, float]:
    """Evaluates image sharpness using the Laplacian Variance method."""
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    if image is None:
        return True, 0.0

    blur_score = float(cv2.Laplacian(image, cv2.CV_64F).var())
    is_blurry = blur_score < threshold

    return is_blurry, blur_score


async def validate_image_quality(file: UploadFile = File(...)) -> tuple[bytes, bool, float]:
    """
    Reusable FastAPI dependency that handles file format checks, file reading,
    and calculates blur scores.
    
    Returns:
        (file_bytes, is_blurry, blur_score)
    """
    # 1. Basic request validation (Protocol/Client errors still raise HTTP 400)
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Upload an image file (.png, .jpg, .jpeg).",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Reset stream pointer so downstream extractors can read if needed
    file.file.seek(0)

    # 2. Pre-processing Blur Evaluation
    is_blurry, blur_score = evaluate_image_blur(file_bytes)

    return file_bytes, is_blurry, blur_score