from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox


class PredictResponse(BaseModel):
    detections: list[Detection]
    threat_level: str
    threat_score: float = Field(ge=0.0, le=1.0)
    image_width: int
    image_height: int
    inference_ms: float


class ModelInfo(BaseModel):
    name: str
    architecture: str
    task: str
    classes: dict[int, str]
    input_size: int
    model_path: str
    weights_size_mb: float


class TrainingMetrics(BaseModel):
    epochs: int
    precision: float
    recall: float
    map50: float
    map50_95: float
    train_box_loss: float
    train_cls_loss: float
    val_box_loss: float
    val_cls_loss: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    classes: list[str]
