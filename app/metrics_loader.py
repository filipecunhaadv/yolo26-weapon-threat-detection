import csv
from pathlib import Path

import yaml

from app.schemas import TrainingMetrics

ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "metrics"


def load_training_metrics() -> TrainingMetrics:
    results_path = METRICS_DIR / "results.csv"
    with results_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    last = rows[-1]
    return TrainingMetrics(
        epochs=len(rows),
        precision=float(last["metrics/precision(B)"]),
        recall=float(last["metrics/recall(B)"]),
        map50=float(last["metrics/mAP50(B)"]),
        map50_95=float(last["metrics/mAP50-95(B)"]),
        train_box_loss=float(last["train/box_loss"]),
        train_cls_loss=float(last["train/cls_loss"]),
        val_box_loss=float(last["val/box_loss"]),
        val_cls_loss=float(last["val/cls_loss"]),
    )


def load_training_args() -> dict:
    args_path = METRICS_DIR / "args.yaml"
    with args_path.open() as f:
        return yaml.safe_load(f)


def list_metric_charts() -> list[str]:
    allowed = {".png", ".jpg", ".jpeg"}
    return sorted(
        p.name
        for p in METRICS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in allowed
    )


def get_chart_path(name: str) -> Path | None:
    path = METRICS_DIR / name
    if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return path
    return None
