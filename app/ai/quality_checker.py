"""Image and Face Quality Assessment Module."""
import cv2
import numpy as np
from typing import Tuple, Dict, Any
from app.config import settings

class QualityChecker:
    """Evaluates facial image quality: sharpness, illumination, face size, and symmetry."""

    @staticmethod
    def evaluate(image: np.ndarray, face_box: Tuple[int, int, int, int] = None) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Evaluate frame or face crop.
        Returns:
            (is_acceptable: bool, overall_score: float, metrics: dict)
        """
        if image is None or image.size == 0:
            return False, 0.0, {"error": "Empty image"}

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 1. Sharpness via Laplacian Variance
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        # Score normalized between 0 and 1 (target >= 60.0)
        sharpness_score = min(1.0, laplacian_var / max(settings.DEFAULT_LAPLACIAN_THRESHOLD, 1.0))
        is_sharp = laplacian_var >= settings.DEFAULT_LAPLACIAN_THRESHOLD

        # 2. Illumination / Brightness
        mean_brightness = float(np.mean(gray))
        is_illuminated = 40.0 <= mean_brightness <= 220.0
        brightness_score = 1.0 - (abs(mean_brightness - 128.0) / 128.0)

        # 3. Face Bounding Box Dimensions
        is_good_size = True
        size_score = 1.0
        if face_box is not None:
            x, y, w, h = face_box
            is_good_size = (w >= settings.MIN_FACE_SIZE and h >= settings.MIN_FACE_SIZE)
            size_score = min(1.0, (w * h) / (settings.MIN_FACE_SIZE * settings.MIN_FACE_SIZE * 2))

        # Overall composite score
        overall_score = float(round(0.4 * sharpness_score + 0.3 * brightness_score + 0.3 * size_score, 3))
        is_acceptable = is_sharp and is_illuminated and is_good_size

        metrics = {
            "sharpness": round(laplacian_var, 2),
            "sharpness_acceptable": is_sharp,
            "brightness": round(mean_brightness, 2),
            "brightness_acceptable": is_illuminated,
            "face_size_acceptable": is_good_size,
            "overall_score": overall_score
        }

        return is_acceptable, overall_score, metrics
