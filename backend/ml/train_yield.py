"""Train the yield model on a real crop-production CSV (e.g. Kaggle 'Crop Production in India',
columns: State_Name, District_Name, Crop_Year, Season, Crop, Area, Production). Put it in backend/data/ .
Run:  python ml/train_yield.py --csv data/crop_production.csv
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

ap = argparse.ArgumentParser(); ap.add_argument("--csv", required=True); a = ap.parse_args()
out = Path(__file__).parent / "artifacts"; out.mkdir(exist_ok=True)
df = pd.read_csv(a.csv); df.columns = [c.strip().lower() for c in df.columns]
df = df.rename(columns={"state_name": "state", "district_name": "district", "crop_year": "year"})
df = df.dropna(subset=["state", "district", "crop", "area", "production", "year"])
for c in ("state", "district"): df[c] = df[c].astype(str).str.strip().str.upper()
df["crop"] = df["crop"].astype(str).str.strip().str.lower(); df["season"] = df["season"].astype(str).str.strip().str.title()
df = df[(df.area > 0) & (df.production >= 0)]
df["yield"] = df.production / df.area                                  # tonnes / hectare
df = df[df["yield"] <= df["yield"].quantile(.995)]
df["log_area"] = np.log1p(df.area)
# note: coconut production is in nuts in many datasets - drop crops whose unit isn't tonnes
df = df[df.crop != "coconut"]
F = ["state", "district", "crop", "season", "log_area", "year"]
Xtr, Xte, ytr, yte = train_test_split(df[F], df["yield"], test_size=.2, random_state=42)
pre = ColumnTransformer([("c", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), F[:4])], remainder="passthrough")
pipe = Pipeline([("p", pre), ("m", HistGradientBoostingRegressor(categorical_features=[0, 1, 2, 3], max_iter=400, learning_rate=.08, random_state=42))])
pipe.fit(Xtr, np.log1p(ytr))
pred = np.expm1(pipe.predict(Xte)); r2 = r2_score(yte, pred); mae = mean_absolute_error(yte, pred)
ratio = (yte.values + 1e-6) / (pred + 1e-6)
pipe.fit(df[F], np.log1p(df["yield"]))                                 # refit on all data for serving
recent = df[df.year >= df.year.max() - 4]
avg = {"district": {k: float(v) for k, v in recent.groupby(["state", "district", "crop"])["yield"].mean().items()},
       "state": {k: float(v) for k, v in recent.groupby(["state", "crop"])["yield"].mean().items()},
       "national": {(k,): float(v) for k, v in recent.groupby("crop")["yield"].mean().items()}}
joblib.dump({"model": pipe, "crops": sorted(df.crop.unique()), "avg": avg,
             "ratio_p10": float(np.percentile(ratio, 10)), "ratio_p90": float(np.percentile(ratio, 90))}, out / "yield_model.joblib")
m = {"holdout_r2": round(float(r2), 3), "holdout_mae_t_per_ha": round(float(mae), 3), "rows": int(len(df)), "csv": a.csv}
(out / "yield_metrics.json").write_text(json.dumps(m, indent=1)); print(m)
