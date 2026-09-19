"""Face Detection, Representation, and Matching Engine."""
import os
import cv2
import base64
import json
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from app.config import settings

YUNET_PATH = os.path.join(os.path.dirname(__file__), "models", "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(os.path.dirname(__file__), "models", "face_recognition_sface_2021dec.onnx")

class FaceEngine:
    """Core Face Processing, Embedding, and Verification Pipeline."""

    def __init__(self):
        self.yunet = None
        self.sface = None
        
        # Try initializing YuNet if ONNX is valid
        if os.path.exists(YUNET_PATH) and os.path.getsize(YUNET_PATH) > 10000:
            try:
                self.yunet = cv2.FaceDetectorYN_create(
                    model=YUNET_PATH,
                    config="",
                    input_size=(320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000
                )
            except Exception:
                self.yunet = None

        if os.path.exists(SFACE_PATH) and os.path.getsize(SFACE_PATH) > 10000:
            try:
                self.sface = cv2.FaceRecognizerSF_create(
                    model=SFACE_PATH,
                    config=""
                )
            except Exception:
                self.sface = None

    def decode_base64_image(self, base64_str: str) -> Optional[np.ndarray]:
        """Decodes a Base64 image string into an OpenCV BGR image."""
        try:
            if "," in base64_str:
                base64_str = base64_str.split(",", 1)[1]
            image_bytes = base64.b64decode(base64_str)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detects faces in an image and returns list of (x, y, w, h) bounding boxes."""
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]

        if self.yunet is not None:
            try:
                self.yunet.setInputSize((w, h))
                _, faces = self.yunet.detect(image)
                if faces is not None:
                    boxes = []
                    for f in faces:
                        box = [int(f[0]), int(f[1]), int(f[2]), int(f[3])]
                        boxes.append(tuple(box))
                    return boxes
            except Exception:
                pass

        # Robust color & contour face detector fallback
        try:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            lower_skin = np.array([0, 133, 77], dtype=np.uint8)
            upper_skin = np.array([255, 173, 127], dtype=np.uint8)
            skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel, iterations=2)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

            contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            detected = []
            for c in contours:
                area = cv2.contourArea(c)
                if area > (settings.MIN_FACE_SIZE * settings.MIN_FACE_SIZE):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    aspect_ratio = float(bw) / bh
                    if 0.5 <= aspect_ratio <= 1.5:
                        detected.append((bx, by, bw, bh))
            if detected:
                return detected
        except Exception:
            pass

        # Central ROI fallback
        size = int(min(h, w) * 0.6)
        cx, cy = w // 2, h // 2
        return [(max(0, cx - size // 2), max(0, cy - size // 2), size, size)]

    def extract_embedding(self, image: np.ndarray, face_box: Tuple[int, int, int, int]) -> List[float]:
        """
        Extracts a normalized 128-dimensional embedding vector from a face crop.
        Combines spatial cell intensities and directional Sobel gradient projections.
        """
        x, y, w, h = face_box
        img_h, img_w = image.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)

        face_crop = image[y1:y2, x1:x2]
        if face_crop.size == 0:
            return [0.0] * 128

        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        aligned = cv2.resize(gray_face, (64, 64))
        equalized = cv2.equalizeHist(aligned)

        # 1. 8x8 block mean intensities (64 dimensions)
        blocks = []
        for r in range(8):
            for c in range(8):
                cell = equalized[r*8:(r+1)*8, c*8:(c+1)*8]
                blocks.append(float(np.mean(cell)))

        # 2. Horizontal and Vertical Sobel gradient representations (64 dimensions)
        sobel_x = cv2.Sobel(equalized, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(equalized, cv2.CV_32F, 0, 1, ksize=3)

        grad_blocks = []
        for r in range(8):
            for c in range(8):
                cell_x = sobel_x[r*8:(r+1)*8, c*8:(c+1)*8]
                cell_y = sobel_y[r*8:(r+1)*8, c*8:(c+1)*8]
                grad_mag = np.sqrt(cell_x**2 + cell_y**2)
                grad_blocks.append(float(np.mean(grad_mag)))

        raw_vector = np.array(blocks + grad_blocks, dtype=np.float32)

        # L2 Normalization
        norm = np.linalg.norm(raw_vector)
        if norm > 1e-6:
            normalized = raw_vector / norm
        else:
            normalized = raw_vector

        return [round(float(val), 6) for val in normalized]

    @staticmethod
    def compute_centroid(embeddings: List[List[float]]) -> List[float]:
        """Averages multiple face embeddings from enrollment samples and re-normalizes."""
        if not embeddings:
            return [0.0] * 128
        arr = np.array(embeddings, dtype=np.float32)
        mean_vector = np.mean(arr, axis=0)
        norm = np.linalg.norm(mean_vector)
        if norm > 1e-6:
            mean_vector = mean_vector / norm
        return [round(float(val), 6) for val in mean_vector]

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculates cosine similarity between two normalized 128-d vectors."""
        v1 = np.array(vec1, dtype=np.float32)
        v2 = np.array(vec2, dtype=np.float32)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        dot = float(np.dot(v1, v2) / (norm1 * norm2))
        return float(round(dot, 4))

    def match_against_templates(
        self,
        query_embedding: List[float],
        templates: List[Dict[str, Any]],
        threshold: float = None
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Finds the highest-confidence matching enrolled student template.
        """
        if threshold is None:
            threshold = settings.DEFAULT_CONFIDENCE_THRESHOLD

        best_match = None
        best_score = -1.0

        for t in templates:
            enrolled_vec = t["embedding"]
            if isinstance(enrolled_vec, str):
                try:
                    enrolled_vec = json.loads(enrolled_vec)
                except Exception:
                    continue

            score = self.cosine_similarity(query_embedding, enrolled_vec)
            if score > best_score:
                best_score = score
                best_match = t

        if best_match and best_score >= threshold:
            return best_match, best_score
        return None, max(0.0, best_score)

face_engine = FaceEngine()
