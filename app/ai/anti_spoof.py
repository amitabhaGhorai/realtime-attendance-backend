"""Presentation Attack Detection (Anti-Spoofing / Liveness Check)."""
import cv2
import numpy as np
from typing import Tuple, Dict, Any

class AntiSpoofDetector:
    """
    Detects presentation attacks (printouts, phone/tablet screens)
    using 2D Fourier high-frequency texture analysis and color spectrum heuristics.
    """

    @staticmethod
    def check_liveness(image: np.ndarray, face_crop: np.ndarray = None) -> Tuple[bool, float, Dict[str, Any]]:
        target = face_crop if (face_crop is not None and face_crop.size > 0) else image
        if target is None or target.size == 0:
            return False, 0.0, {"reason": "Invalid image crop"}

        if len(target.shape) == 3:
            gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(target, cv2.COLOR_BGR2HSV)
        else:
            gray = target
            hsv = None

        # Resize to standard analysis size
        resized = cv2.resize(gray, (128, 128))

        # 1. 2D Discrete Fourier Transform (FFT) for high frequency moire / texture
        f = np.fft.fft2(resized)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-9)

        # High frequency energy in outer rim
        rows, cols = resized.shape
        crow, ccol = rows // 2, cols // 2
        # Mask center low-frequencies
        r = 25
        y, x = np.ogrid[:rows, :cols]
        mask = (x - ccol) ** 2 + (y - crow) ** 2 >= r * r
        high_freq_energy = float(np.mean(magnitude_spectrum[mask]))

        # Printed photos and digital screens typically exhibit unnatural frequency cuts or moire peaks
        # Natural human faces with skin texture maintain high frequency energy within [65, 145]
        texture_score = float(np.clip((high_freq_energy - 40.0) / 80.0, 0.0, 1.0))
        is_texture_valid = 50.0 <= high_freq_energy <= 155.0

        # 2. Color Saturation & Natural Skin Tones (if color image)
        color_score = 1.0
        if hsv is not None:
            sat_mean = float(np.mean(hsv[:, :, 1]))
            # Paper prints often have extremely low saturation or unnatural hue shifts
            if sat_mean < 15.0 or sat_mean > 210.0:
                color_score = 0.5

        confidence = round(float(0.7 * texture_score + 0.3 * color_score), 3)
        is_live = is_texture_valid and (confidence >= 0.45)

        details = {
            "high_freq_energy": round(high_freq_energy, 2),
            "texture_score": round(texture_score, 3),
            "confidence": confidence,
            "is_live": is_live
        }
        return is_live, confidence, details
