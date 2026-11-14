"""Train and evaluate the disease classifier on PlantVillage train/test folders."""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.ml_infer import extract_features


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_split(split_dir):
    features, labels, counts = [], [], {}
    classes = sorted(path for path in split_dir.iterdir() if path.is_dir())
    for class_dir in classes:
        for image_path in sorted(class_dir.rglob("*")):
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                with Image.open(image_path) as image:
                    features.append(extract_features(image))
            except (OSError, ValueError) as exc:
                raise ValueError(f"Unable to read PlantVillage image: {image_path}") from exc
            labels.append(class_dir.name)
            counts[class_dir.name] = counts.get(class_dir.name, 0) + 1
    if not features:
        raise ValueError(f"No labelled images found under {split_dir}")
    return np.vstack(features), np.asarray(labels), counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Directory containing train/ and test/ class folders")
    args = parser.parse_args()
    source = Path(args.data)
    train_dir, test_dir = source / "train", source / "test"
    if not train_dir.is_dir() or not test_dir.is_dir():
        raise FileNotFoundError("PlantVillage data must contain separate train/ and test/ class folders.")

    print("Extracting PlantVillage training features...")
    X_train, y_train, train_counts = load_split(train_dir)
    print("Extracting held-out PlantVillage test features...")
    X_test, y_test, test_counts = load_split(test_dir)
    if set(train_counts) != set(test_counts):
        raise ValueError("PlantVillage train and test splits must contain the same classes.")
    if min(train_counts.values()) < 2 or min(test_counts.values()) < 1:
        raise ValueError("Every class needs at least two training and one test image.")

    classifier = SGDClassifier(
        loss="log_loss",
        alpha=0.0001,
        max_iter=30,
        tol=0.001,
        random_state=42,
        class_weight="balanced",
        n_jobs=1,
    )
    classifier.fit(X_train, y_train)
    predictions = classifier.predict(X_test)
    classes = classifier.classes_.tolist()
    metrics = {
        "dataset": "PlantVillage RGB color images",
        "dataset_citation": "Mohanty, Hughes, and Salathé (2016), DOI: 10.3389/fpls.2016.01419",
        "license": "CC BY-SA 3.0",
        "train_images": int(len(y_train)),
        "test_images": int(len(y_test)),
        "classes": len(classes),
        "class_counts": {label: train_counts[label] + test_counts[label] for label in classes},
        "test_accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "test_macro_f1": round(float(f1_score(y_test, predictions, average="macro", zero_division=0)), 4),
        "split": "published PlantVillage leaf-grouped train/test split",
        "model": "32x32 HOG and RGB/HSV histograms with SGD logistic classifier",
        "caveat": "PlantVillage contains controlled-image samples. Test accuracy is not field-photo accuracy or a confirmed diagnosis.",
    }

    out = BACKEND / "ml" / "artifacts"
    out.mkdir(exist_ok=True)
    joblib.dump({"kind": "plantvillage_hog_v1", "classifier": classifier}, out / "disease_model.joblib")
    (out / "classes.json").write_text(json.dumps(classes, indent=2), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    np.savetxt(
        out / "confusion_matrix.csv",
        confusion_matrix(y_test, predictions, labels=classes),
        fmt="%d",
        delimiter=",",
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
