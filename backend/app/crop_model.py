"""Optional crop suitability predictions from a locally trained crop model."""
import json
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
MODEL_PATH = ART / "crop_recommendation.joblib"
_bundle = None


def ready():
    return MODEL_PATH.is_file()


def info():
    metrics_path = ART / "crop_metrics.json"
    if not metrics_path.is_file():
        return None
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def predict(nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall):
    global _bundle
    if not ready():
        raise FileNotFoundError("Crop model is not trained. Run backend/ml/train_crop.py (see README).")

    if _bundle is None:
        import joblib

        _bundle = joblib.load(MODEL_PATH)
        if _bundle.get("kind") != "crop_recommendation_rf_v1":
            raise ValueError("Crop model artifact has an unsupported format.")

    values = [nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall]
    features = np.asarray(
        [[float(value) if value is not None else np.nan for value in values]],
        dtype=np.float32,
    )
    pipeline = _bundle["pipeline"]
    probabilities = pipeline.predict_proba(features)[0]
    classes = pipeline.named_steps["classifier"].classes_
    top = probabilities.argsort()[::-1][:3]
    notes = []
    if ph is None:
        notes.append("Soil pH was not entered; the model used the training-set median.")
    return {
        "results": [
            {"crop": str(classes[index]), "confidence": round(float(probabilities[index]), 4)}
            for index in top
        ],
        "metrics": info(),
        "input_notes": notes,
        "disclaimer": "Dataset-based suitability suggestions are not field-validated advice. Confirm with a local agricultural expert.",
    }
