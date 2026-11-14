"""Train the crop suitability classifier from a licensed NPK/climate CSV."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="backend/data/crop_recommendation.csv")
    args = parser.parse_args()

    source = Path(args.csv)
    if not source.is_file():
        raise FileNotFoundError(f"Crop recommendation CSV not found: {source}")
    frame = pd.read_csv(source)
    frame.columns = [str(column).strip() for column in frame.columns]
    label_column = next((column for column in frame.columns if column.lower() == "label"), None)
    feature_columns = {
        column.lower(): column
        for column in frame.columns
        if column.lower() in {feature.lower() for feature in FEATURES}
    }
    missing = [name for name in FEATURES if name.lower() not in feature_columns]
    if label_column is None or missing:
        raise ValueError("CSV must contain N, P, K, temperature, humidity, ph, rainfall, and label columns.")

    X = frame[[feature_columns[name.lower()] for name in FEATURES]].apply(pd.to_numeric, errors="coerce")
    y = frame[label_column].astype("string").str.strip()
    valid = X.notna().any(axis=1) & y.notna() & y.ne("")
    X, y = X.loc[valid].to_numpy(dtype=np.float32), y.loc[valid].astype(str)
    if y.nunique() < 2 or y.value_counts().min() < 2:
        raise ValueError("Each crop class must have at least two valid rows.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            random_state=42,
            class_weight="balanced",
            min_samples_leaf=2,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)
    prediction = pipeline.predict(X_test)
    metrics = {
        "dataset": "user-provided crop recommendation CSV",
        "rows": int(len(y)),
        "classes": int(y.nunique()),
        "test_rows": int(len(y_test)),
        "test_accuracy": round(float(accuracy_score(y_test, prediction)), 4),
        "test_macro_f1": round(float(f1_score(y_test, prediction, average="macro", zero_division=0)), 4),
        "split": "stratified random 80/20 holdout",
        "caveat": "The benchmark score is not a field trial. Use a dataset whose license permits model training and distribution.",
    }

    pipeline.fit(X, y)
    out = Path(__file__).parent / "artifacts"
    out.mkdir(exist_ok=True)
    joblib.dump({"kind": "crop_recommendation_rf_v1", "pipeline": pipeline}, out / "crop_recommendation.joblib")
    (out / "crop_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
