"""Train the yield model on a real crop-production CSV (e.g. Kaggle 'Crop Production in India',
columns: State_Name, District_Name, Crop_Year, Season, Crop, Area, Production). Put it in backend/data/ .
Run:  python ml/train_yield.py --csv data/crop_production.csv
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
a = ap.parse_args()
out = Path(__file__).parent / "artifacts"; out.mkdir(exist_ok=True)
df = pd.read_csv(a.csv); df.columns = [c.strip().lower() for c in df.columns]
df = df.rename(columns={"state_name": "state", "district_name": "district", "crop_year": "year"})
df = df.dropna(subset=["state", "district", "crop", "area", "production", "year"])
for c in ("state", "district"): df[c] = df[c].astype(str).str.strip().str.upper()
df["crop"] = df["crop"].astype(str).str.strip().str.lower(); df["season"] = df["season"].astype(str).str.strip().str.title()
df = df[(df.area > 0) & (df.production >= 0)]
df["yield"] = df.production / df.area                                  # tonnes / hectare
# note: coconut production is in nuts in many datasets - drop crops whose unit isn't tonnes
df = df[df.crop != "coconut"]
year_counts = df["year"].value_counts().sort_index()
if len(year_counts) < 3:
    raise ValueError("The dataset needs at least three years of crop production for a chronological test.")
# Ignore a sparse final year, which is usually an incomplete reporting year.
if year_counts.iloc[-1] < year_counts.median() * .1:
    df = df[df.year < year_counts.index[-1]]
years = np.sort(df.year.unique())
holdout_start = years[max(1, int(len(years) * .8))]
train_df = df[df.year < holdout_start].copy()
test_df = df[df.year >= holdout_start].copy()
if train_df.empty or test_df.empty:
    raise ValueError("Could not create a chronological holdout split from the dataset years.")
yield_ceiling = train_df["yield"].quantile(.995)
excluded_test_rows = int((test_df["yield"] > yield_ceiling).sum())
train_df = train_df[train_df["yield"] <= yield_ceiling]
test_df = test_df[test_df["yield"] <= yield_ceiling]
if train_df.empty or test_df.empty:
    raise ValueError("Yield outlier filtering left an empty training or test split.")

districts = train_df["district"].value_counts().head(254).index
train_df.loc[~train_df["district"].isin(districts), "district"] = "OTHER"
test_df.loc[~test_df["district"].isin(districts), "district"] = "OTHER"
df.loc[~df["district"].isin(districts), "district"] = "OTHER"
df = df[df["yield"] <= yield_ceiling].copy()
df["log_area"] = np.log1p(df.area)
train_df["log_area"] = np.log1p(train_df.area)
test_df["log_area"] = np.log1p(test_df.area)
F = ["state", "district", "crop", "season", "log_area", "year"]
pre = ColumnTransformer([("c", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), F[:4])], remainder="passthrough")
pipe = Pipeline([("p", pre), ("m", HistGradientBoostingRegressor(categorical_features=[0, 1, 2, 3], max_iter=400, learning_rate=.08, random_state=42))])
pipe.fit(train_df[F], np.log1p(train_df["yield"]))
pred = np.maximum(0, np.expm1(pipe.predict(test_df[F])))
yte = test_df["yield"].to_numpy()
r2 = r2_score(yte, pred); mae = mean_absolute_error(yte, pred)
rmse = float(np.sqrt(mean_squared_error(yte, pred)))
ratio = (yte + 1e-6) / (pred + 1e-6)
pipe.fit(df[F], np.log1p(df["yield"]))                                 # refit on all valid history for serving
recent = df[df.year >= df.year.max() - 4]
avg = {"district": {k: float(v) for k, v in recent.groupby(["state", "district", "crop"])["yield"].mean().items()},
       "state": {k: float(v) for k, v in recent.groupby(["state", "crop"])["yield"].mean().items()},
       "national": {(k,): float(v) for k, v in recent.groupby("crop")["yield"].mean().items()}}
joblib.dump({"model": pipe, "crops": sorted(df.crop.unique()), "avg": avg,
             "districts": sorted(districts), "ratio_p10": float(np.percentile(ratio, 10)),
             "ratio_p90": float(np.percentile(ratio, 90))}, out / "yield_model.joblib")
m = {"holdout_r2": round(float(r2), 3), "holdout_mae_t_per_ha": round(float(mae), 3),
     "holdout_rmse_t_per_ha": round(rmse, 3), "rows": int(len(df)),
     "train_rows": int(len(train_df)), "test_rows": int(len(test_df)),
     "train_years": [int(train_df.year.min()), int(train_df.year.max())],
     "test_years": [int(test_df.year.min()), int(test_df.year.max())],
     "outlier_test_rows_excluded": excluded_test_rows, "csv": Path(a.csv).name,
     "caveat": "The dataset's redistribution license is unverified. Regional historical estimates are not farm-level measurements."}
(out / "yield_metrics.json").write_text(json.dumps(m, indent=1)); print(m)
