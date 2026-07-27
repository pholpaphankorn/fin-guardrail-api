import cv2
import numpy as np

# Standard variance threshold for document OCR. 
# Scores < 100.0 usually indicate heavy blur/unreadable text.
DEFAULT_BLUR_THRESHOLD = 100.0


def evaluate_image_blur(file_bytes: bytes, threshold: float = DEFAULT_BLUR_THRESHOLD) -> tuple[bool, float]:
    """
    Evaluates image sharpness using the Laplacian Variance method.
    
    Returns:
        is_blurry (bool): True if the image focus variance is below the acceptable threshold.
        blur_score (float): The calculated variance score (higher = sharper).
    """
    # Convert file bytes into an OpenCV grayscale image array
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    if image is None:
        # Unable to decode image data
        return True, 0.0

    # Compute the Laplacian variance (focus metric)
    blur_score = float(cv2.Laplacian(image, cv2.CV_64F).var())
    is_blurry = blur_score < threshold

    return is_blurry, blur_score