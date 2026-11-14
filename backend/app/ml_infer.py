"""PlantVillage disease inference using the trained HOG + SGD classifier."""
import io
import json
import os
from pathlib import Path

ART = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
MIN_CONF = float(os.getenv("DISEASE_MIN_CONFIDENCE", "0.80"))
_model, _classes = None, None


class ModelNotReady(Exception):
    pass


def ready():
    return (ART / "disease_model.joblib").exists() and (ART / "classes.json").exists()


def model_info():
    p = ART / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def _load():
    global _model, _classes
    if _model is None:
        if not ready():
            raise ModelNotReady("Disease model is not trained yet. Run backend/ml/train_disease.py (see README).")
        import joblib

        bundle = joblib.load(ART / "disease_model.joblib")
        if bundle.get("kind") != "plantvillage_hog_v1":
            raise ValueError("Disease model artifact has an unsupported format.")
        _model = bundle["classifier"]
        _classes = json.loads((ART / "classes.json").read_text(encoding="utf-8"))
        if list(_model.classes_) != _classes:
            raise ValueError("Disease model classes do not match classes.json.")
    return _model, _classes


def extract_features(image):
    import numpy as np
    from PIL import Image

    image_size, cell_size, bins = 32, 8, 9
    rgb_image = image.convert("RGB").resize((image_size, image_size), Image.Resampling.BILINEAR)
    rgb = np.asarray(rgb_image, dtype=np.float32)
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    gradient_y, gradient_x = np.gradient(gray)
    magnitude = np.hypot(gradient_x, gradient_y)
    orientation = np.mod(np.arctan2(gradient_y, gradient_x), np.pi) * (bins / np.pi)
    lower_bin = np.floor(orientation).astype(np.int32) % bins
    bin_fraction = orientation - np.floor(orientation)
    cell_rows, cell_columns = np.indices((image_size, image_size))
    cell_count = image_size // cell_size
    cell_ids = ((cell_rows // cell_size) * cell_count + cell_columns // cell_size).ravel()
    magnitude = magnitude.ravel()
    lower_bin = lower_bin.ravel()
    bin_fraction = bin_fraction.ravel()
    cell_total = cell_count * cell_count
    cell_histograms = np.zeros((cell_total, bins), dtype=np.float32)
    for bin_index in range(bins):
        lower_weights = magnitude * (1 - bin_fraction) * (lower_bin == bin_index)
        upper_weights = magnitude * bin_fraction * (((lower_bin + 1) % bins) == bin_index)
        cell_histograms[:, bin_index] = (
            np.bincount(cell_ids, weights=lower_weights, minlength=cell_total)
            + np.bincount(cell_ids, weights=upper_weights, minlength=cell_total)
        )
    cell_histograms = cell_histograms.reshape(cell_count, cell_count, bins)
    cell_histograms /= np.maximum(np.linalg.norm(cell_histograms, axis=2, keepdims=True), 1e-6)

    color_histograms = []
    hsv = np.asarray(rgb_image.convert("HSV"), dtype=np.uint8)
    for channel in range(3):
        color_histograms.extend(
            np.histogram(rgb[:, :, channel], bins=16, range=(0, 256))[0].astype(np.float32)
            / (image_size * image_size)
        )
        color_histograms.extend(
            np.histogram(hsv[:, :, channel], bins=16, range=(0, 256))[0].astype(np.float32)
            / (image_size * image_size)
        )
    return np.concatenate([cell_histograms.ravel(), color_histograms]).astype(np.float32)


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
    with Image.open(io.BytesIO(image_bytes)) as source:
        features = extract_features(source).reshape(1, -1)
    probs = model.predict_proba(features)[0]
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
