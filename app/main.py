import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.detector import WeaponThreatDetector
from app.metrics_loader import (
    get_chart_path,
    list_metric_charts,
    load_training_args,
    load_training_metrics,
)
from app.schemas import HealthResponse, ModelInfo

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "model" / "best.pt"))

detector: WeaponThreatDetector | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global detector
    detector = WeaponThreatDetector(MODEL_PATH)
    yield


app = FastAPI(
    title="YOLO26 Weapon Threat Detection API",
    description=(
        "API de detecção de ameaças visuais com YOLO26. "
        "Identifica armas (gun, knife) e pessoas com máscara (person_with_mask)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded=detector is not None,
        classes=list(detector.class_names.values()) if detector else [],
    )


@app.get("/model/info", response_model=ModelInfo)
async def model_info() -> ModelInfo:
    if detector is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    args = load_training_args()

    return ModelInfo(
        name="weapon_threat_detection_yolo26",
        architecture=args.get("model", "yolo26s.pt"),
        task=detector.model.task,
        classes=detector.class_names,
        input_size=detector.input_size,
        model_path=str(MODEL_PATH),
        weights_size_mb=round(size_mb, 2),
    )


@app.get("/metrics")
async def metrics() -> JSONResponse:
    training = load_training_metrics()
    args = load_training_args()
    return JSONResponse(
        {
            "training": training.model_dump(),
            "config": {
                "epochs": args.get("epochs"),
                "batch": args.get("batch"),
                "imgsz": args.get("imgsz"),
                "optimizer": args.get("optimizer"),
                "dataset": args.get("data"),
            },
            "charts": list_metric_charts(),
        }
    )


@app.get("/metrics/charts/{chart_name}")
async def metric_chart(chart_name: str) -> FileResponse:
    path = get_chart_path(chart_name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Gráfico não encontrado: {chart_name}")
    return FileResponse(path)


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    conf: float = Query(0.25, ge=0.0, le=1.0),
    iou: float = Query(0.7, ge=0.0, le=1.0),
    annotated: bool = Query(False, description="Incluir imagem anotada em base64"),
) -> JSONResponse:
    if detector is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Imagem vazia")

    image = detector.load_image(data)

    if annotated:
        result, annotated_image = detector.predict_annotated(image, conf=conf, iou=iou)
        payload = result.model_dump()
        payload["annotated_image_base64"] = detector.image_to_base64(annotated_image)
        return JSONResponse(payload)

    result = detector.predict(image, conf=conf, iou=iou)
    return JSONResponse(result.model_dump())
