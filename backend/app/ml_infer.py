"""Disease inference. Needs ml/artifacts/disease_model.keras + classes.json (created by ml/train_disease.py)."""
import io, os, json
from pathlib import Path

ART = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
MIN_CONF = float(os.getenv("DISEASE_MIN_CONFIDENCE", "0.80"))
_model, _classes = None, None


class ModelNotReady(Exception):
    pass


def ready():
    return (ART / "disease_model.keras").exists() and (ART / "classes.json").exists()


def model_info():
    p = ART / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def _load():
    global _model, _classes
    if _model is None:
        if not ready():
            raise ModelNotReady("Disease model is not trained yet. Run backend/ml/train_disease.py (see README).")
        import tensorflow as tf
        _model = tf.keras.models.load_model(ART / "disease_model.keras")
        _classes = json.loads((ART / "classes.json").read_text())
    return _model, _classes


def _split(label):
    crop, _, dis = label.partition("___")
    crop = crop.replace("_", " ").replace(",", "").strip()
    dis = dis.replace("_", " ").strip()
    return crop, dis, dis.lower() == "healthy"


ADVICE = [  # (keywords, prevention, organic, chemical)
    (("blight", "spot", "rust", "scab", "mold", "mildew", "rot", "mite", "scorch"),
     "Remove and destroy infected leaves/debris, avoid overhead irrigation, keep spacing for airflow, rotate crops, use clean seed/seedlings.",
     "Neem-based or copper-based sprays permitted under organic standards; improve drainage.",
     "Use only a fungicide/pesticide recommended for this crop by your state agricultural university or KVK, as per label. Do not exceed label dose."),
    (("virus", "curl", "mosaic"),
     "Control insect vectors (whitefly/aphids), remove infected plants early, use virus-free planting material, control weeds.",
     "Yellow sticky traps, neem-based vector control.",
     "There is no cure for viral diseases; vector-control products must be locally approved - ask your KVK."),
]


def advice_for(disease, healthy):
    if healthy:
        return {"prevention": "Plant looks healthy. Keep scouting regularly, maintain balanced nutrition and irrigation.",
                "organic": "-", "chemical": "No treatment needed.", "nutrient_note": None, "follow_up": "Re-check in 7-10 days."}
    d = disease.lower()
    for kws, prev, org, chem in ADVICE:
        if any(k in d for k in kws):
            return {"prevention": prev, "organic": org, "chemical": chem,
                    "nutrient_note": "Nutrient correction is separate from disease treatment - fertiliser does not cure this disease. Test soil before adding nutrients.",
                    "follow_up": "Re-photograph affected plants after 5-7 days and check whether it is spreading."}
    return {"prevention": "Isolate affected plants and avoid moving tools/water between healthy and infected plants.",
            "organic": "Consult an agriculture expert for organic options.", "chemical": "Consult KVK / agriculture officer for approved products.",
            "nutrient_note": "Nutrient correction is separate from disease treatment.", "follow_up": "Re-check in a week."}


def predict(image_bytes: bytes, selected_crop: str | None = None):
    import numpy as np
    from PIL import Image
    model, classes = _load()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
    probs = model.predict(np.expand_dims(np.asarray(img, dtype="float32"), 0), verbose=0)[0]
    top = probs.argsort()[::-1][:3]
    preds = [{"label": classes[i], "confidence": float(probs[i])} for i in top]
    crop, disease, healthy = _split(preds[0]["label"])
    conf = preds[0]["confidence"]
    mismatch = bool(selected_crop) and selected_crop.strip().lower() not in crop.lower() and crop.lower() not in selected_crop.strip().lower()
    confident = conf >= MIN_CONF and not mismatch
    out = {"crop_detected": crop, "disease": disease, "healthy": healthy, "confidence": conf, "confident": confident,
           "top3": [{"label": p["label"].replace("___", " - ").replace("_", " "), "confidence": p["confidence"]} for p in preds],
           "severity": "Not assessed - the classifier identifies disease type, it does not measure severity.",
           "category": "Healthy" if healthy else ("Viral" if any(k in disease.lower() for k in ("virus", "curl", "mosaic")) else
                       "Pest (mite)" if "mite" in disease.lower() else "Fungal / bacterial (likely)"),
           "mismatch": mismatch}
    if confident:
        out["advice"] = advice_for(disease, healthy)
        out["message"] = "AI suggestion - not a confirmed diagnosis. Confirm with an agriculture expert before treating."
    else:
        out["message"] = ("The selected crop does not match what the model sees. " if mismatch else "") + \
                         "The model is not confident. Upload a clearer, close-up photo of one affected leaf in daylight, or consult an agriculture expert."
    return out
