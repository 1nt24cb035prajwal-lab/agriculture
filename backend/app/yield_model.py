"""Yield prediction using a model trained by ml/train_yield.py on a real crop-production dataset."""
import json
from pathlib import Path
from datetime import date, timedelta

ART = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
_bundle = None
ALIAS = {"soybean": "soyabean", "mustard": "rapeseed &mustard", "cotton": "cotton(lint)", "chilli": "dry chillies",
         "paddy": "rice", "ragi": "ragi", "jowar": "jowar", "bajra": "bajra", "groundnut": "groundnut"}
SEASON = {"kharif": "Kharif", "rabi": "Rabi", "summer": "Summer", "zaid": "Summer", "autumn": "Autumn", "winter": "Winter"}


class ModelNotReady(Exception):
    pass


def ready():
    return (ART / "yield_model.joblib").exists()


def _load():
    global _bundle
    if _bundle is None:
        if not ready():
            raise ModelNotReady("Yield model not trained. Put a crop-production CSV in backend/data/ and run ml/train_yield.py (see README).")
        import joblib
        _bundle = joblib.load(ART / "yield_model.joblib")
    return _bundle


def info():
    p = ART / "yield_metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def predict(farm: dict, crop_days: int | None):
    import pandas as pd
    b = _load()
    crop = ALIAS.get((farm["crop"] or "").strip().lower(), (farm["crop"] or "").strip().lower())
    state = (farm.get("state") or "").strip().upper()
    district = (farm.get("district") or "").strip().upper()
    season = SEASON.get((farm.get("season") or "").strip().lower(), "Whole Year")
    ha = farm["area"] * (0.404686 if (farm.get("unit") or "acres") == "acres" else 1)
    if crop not in b["crops"]:
        raise ModelNotReady(f"Crop '{farm['crop']}' is not in the training dataset.")
    X = pd.DataFrame([{"state": state, "district": district, "crop": crop, "season": season, "log_area": __import__("math").log1p(ha), "year": date.today().year}])
    y = float(b["model"].predict(X)[0])
    y = max(y, 0.0)
    lo, hi = y * b["ratio_p10"], y * b["ratio_p90"]
    avg = b["avg"]
    ref, level = None, None
    for lvl, key in (("district", (state, district, crop)), ("state", (state, crop)), ("national", (crop,))):
        if key in avg[lvl]:
            ref, level = avg[lvl][key], lvl; break
    harvest = None
    if farm.get("harvest_date"):
        harvest = farm["harvest_date"]
    elif farm.get("start_date") and crop_days:
        try: harvest = (date.fromisoformat(farm["start_date"]) + timedelta(days=crop_days)).isoformat()
        except ValueError: pass
    per_acre = y * 0.404686
    return {"source_label": "Model prediction (trained on historical district-level data)",
            "yield_t_per_ha": round(y, 2), "yield_t_per_acre": round(per_acre, 2), "total_tonnes": round(y * ha, 2),
            "range_t_per_acre": [round(lo * 0.404686, 2), round(hi * 0.404686, 2)],
            "regional_avg": None if ref is None else {"t_per_ha": round(ref, 2), "t_per_acre": round(ref * 0.404686, 2), "level": level,
                                                      "label": f"Historical dataset average ({level} level)"},
            "diff_pct": None if not ref else round((y - ref) / ref * 100, 1),
            "harvest_date": harvest, "season_used": season,
            "district_matched": (state, district, crop) in avg["district"], "model_quality": info(),
            "disclaimer": "Statistical estimate from historical production data. It does not use this season's weather, NDVI or disease - those appear only as qualitative factors."}
