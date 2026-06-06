import base64
import io
import time
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

from app.schemas import BoundingBox, Detection, PredictResponse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = ROOT / "model" / "best.pt"

THREAT_WEIGHTS = {
    "gun": 1.0,
    "knife": 0.85,
    "person_with_mask": 0.6,
}

# Bônus por detecção adicional além da primeira (máx. +0.30)
QUANTITY_BONUS_PER_DETECTION = 0.05
MAX_QUANTITY_BONUS = 0.30


class WeaponThreatDetector:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo não encontrado: {self.model_path}")
        self.model = YOLO(str(self.model_path))
        self.class_names: dict[int, str] = dict(self.model.names)
        self.input_size = 640

    def predict(
        self,
        image: Image.Image,
        conf: float = 0.25,
        iou: float = 0.7,
    ) -> PredictResponse:
        start = time.perf_counter()
        results = self.model.predict(
            source=image,
            conf=conf,
            iou=iou,
            imgsz=self.input_size,
            verbose=False,
        )
        inference_ms = (time.perf_counter() - start) * 1000

        width, height = image.size
        detections: list[Detection] = []

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls.item())
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=self.class_names[cls_id],
                        confidence=confidence,
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )

        threat_score, threat_level, detection_count, class_counts = self._assess_threat(
            detections
        )

        return PredictResponse(
            detections=detections,
            detection_count=detection_count,
            class_counts=class_counts,
            threat_level=threat_level,
            threat_score=threat_score,
            image_width=width,
            image_height=height,
            inference_ms=round(inference_ms, 2),
        )

    def predict_annotated(
        self,
        image: Image.Image,
        conf: float = 0.25,
        iou: float = 0.7,
    ) -> tuple[PredictResponse, Image.Image]:
        start = time.perf_counter()
        results = self.model.predict(
            source=image,
            conf=conf,
            iou=iou,
            imgsz=self.input_size,
            verbose=False,
        )
        inference_ms = (time.perf_counter() - start) * 1000

        width, height = image.size
        detections: list[Detection] = []

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls.item())
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=self.class_names[cls_id],
                        confidence=confidence,
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )

        annotated = Image.fromarray(results[0].plot())
        threat_score, threat_level, detection_count, class_counts = self._assess_threat(
            detections
        )

        response = PredictResponse(
            detections=detections,
            detection_count=detection_count,
            class_counts=class_counts,
            threat_level=threat_level,
            threat_score=threat_score,
            image_width=width,
            image_height=height,
            inference_ms=round(inference_ms, 2),
        )
        return response, annotated

    def _assess_threat(
        self, detections: list[Detection]
    ) -> tuple[float, str, int, dict[str, int]]:
        if not detections:
            return 0.0, "none", 0, {}

        class_counts: dict[str, int] = {}
        for det in detections:
            class_counts[det.class_name] = class_counts.get(det.class_name, 0) + 1

        detection_count = len(detections)
        individual_scores = [
            det.confidence * THREAT_WEIGHTS.get(det.class_name, 0.5)
            for det in detections
        ]
        peak_score = max(individual_scores)
        quantity_bonus = min(
            (detection_count - 1) * QUANTITY_BONUS_PER_DETECTION,
            MAX_QUANTITY_BONUS,
        )
        threat_score = min(peak_score + quantity_bonus, 1.0)
        threat_level = self._resolve_threat_level(
            threat_score, detection_count, class_counts
        )

        return round(threat_score, 4), threat_level, detection_count, class_counts

    @staticmethod
    def _resolve_threat_level(
        threat_score: float,
        detection_count: int,
        class_counts: dict[str, int],
    ) -> str:
        gun_count = class_counts.get("gun", 0)
        knife_count = class_counts.get("knife", 0)
        weapon_count = gun_count + knife_count

        if threat_score >= 0.85 and detection_count >= 4:
            return "critical"
        if threat_score >= 0.75 or (weapon_count >= 3 and threat_score >= 0.55):
            return "high"
        if threat_score >= 0.45 or (detection_count >= 3 and threat_score >= 0.35):
            return "medium"
        return "low"

    @staticmethod
    def image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
        buffer = io.BytesIO()
        image.save(buffer, format=fmt)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def load_image(data: bytes) -> Image.Image:
        return Image.open(io.BytesIO(data)).convert("RGB")
