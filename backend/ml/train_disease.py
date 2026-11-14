"""Train and evaluate the disease classifier on PlantVillage train/test folders."""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
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
PLANTDOC_LABELS = {
    "Apple leaf": "Apple___healthy",
    "Apple rust leaf": "Apple___Cedar_apple_rust",
    "Apple Scab Leaf": "Apple___Apple_scab",
    "Bell_pepper leaf": "Pepper,_bell___healthy",
    "Bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "Blueberry leaf": "Blueberry___healthy",
    "Cherry leaf": "Cherry_(including_sour)___healthy",
    "Corn Gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf": "Corn_(maize)___Common_rust_",
    "grape leaf": "Grape___healthy",
    "grape leaf black rot": "Grape___Black_rot",
    "Peach leaf": "Peach___healthy",
    "Potato leaf early blight": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Raspberry leaf": "Raspberry___healthy",
    "Soyabean leaf": "Soybean___healthy",
    "Squash Powdery mildew leaf": "Squash___Powdery_mildew",
    "Strawberry leaf": "Strawberry___healthy",
    "Tomato Early blight leaf": "Tomato___Early_blight",
    "Tomato leaf": "Tomato___healthy",
    "Tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "Tomato leaf late blight": "Tomato___Late_blight",
    "Tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato mold leaf": "Tomato___Leaf_Mold",
    "Tomato Septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "Tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
}


def extract_image(item):
    image_path, label, dataset_name = item
    try:
        with Image.open(image_path) as image:
            return extract_features(image), label
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unable to read {dataset_name} image: {image_path}") from exc


def load_split(split_dir, label_map=None, dataset_name="disease"):
    features, labels, counts = [], [], {}
    image_paths = []
    classes = sorted(path for path in split_dir.iterdir() if path.is_dir())
    for class_dir in classes:
        label = class_dir.name
        if label_map is not None:
            if label not in label_map:
                raise ValueError(f"Unmapped {dataset_name} class: {label}")
            label = label_map[label]
        for image_path in sorted(class_dir.rglob("*")):
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            image_paths.append((image_path, label, dataset_name))
    if not image_paths:
        raise ValueError(f"No labelled images found under {split_dir}")
    workers = min(4, os.cpu_count() or 1)
    print(f"Extracting {len(image_paths)} {dataset_name} images with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for start in range(0, len(image_paths), 1000):
            batch = image_paths[start:start + 1000]
            for feature, label in executor.map(extract_image, batch):
                features.append(feature)
                labels.append(label)
                counts[label] = counts.get(label, 0) + 1
            print(f"Extracted {min(start + len(batch), len(image_paths))}/{len(image_paths)} {dataset_name} images")
    if not features:
        raise ValueError(f"No labelled images found under {split_dir}")
    return np.vstack(features), np.asarray(labels), counts


def load_dataset(data_dir, label_map=None, dataset_name="disease"):
    train_dir, test_dir = data_dir / "train", data_dir / "test"
    if not train_dir.is_dir() or not test_dir.is_dir():
        raise FileNotFoundError(f"{dataset_name} data must contain separate train/ and test/ class folders.")
    X_train, y_train, train_counts = load_split(train_dir, label_map, dataset_name)
    X_test, y_test, test_counts = load_split(test_dir, label_map, dataset_name)
    if label_map is None and set(train_counts) != set(test_counts):
        raise ValueError(f"{dataset_name} train and test splits must contain the same classes.")
    if min(train_counts.values()) < 2 or min(test_counts.values()) < 1:
        raise ValueError(f"Every {dataset_name} class needs at least two training and one test image.")
    return X_train, y_train, train_counts, X_test, y_test, test_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="PlantVillage directory containing train/ and test/ class folders")
    parser.add_argument("--plantdoc-data", help="Optional PlantDoc directory with train/ and test/ class folders")
    parser.add_argument("--output", help="Artifact directory (defaults to backend/ml/artifacts)")
    args = parser.parse_args()
    source = Path(args.data)
    print("Extracting PlantVillage train/test features...")
    X_train, y_train, train_counts, X_test, y_test, test_counts = load_dataset(source, dataset_name="PlantVillage")
    plantdoc_test = None
    dataset_weights = np.ones(len(y_train), dtype=np.float64)
    if args.plantdoc_data:
        print("Extracting PlantDoc train/test features...")
        px_train, py_train, plantdoc_train_counts, px_test, py_test, plantdoc_test_counts = load_dataset(
            Path(args.plantdoc_data), PLANTDOC_LABELS, "PlantDoc"
        )
        dataset_weights = np.concatenate([
            np.ones(len(y_train), dtype=np.float64),
            np.full(len(py_train), len(y_train) / len(py_train), dtype=np.float64),
        ])
        X_train = np.vstack([X_train, px_train])
        y_train = np.concatenate([y_train, py_train])
        train_counts = {
            label: train_counts.get(label, 0) + plantdoc_train_counts.get(label, 0)
            for label in set(train_counts) | set(plantdoc_train_counts)
        }
        plantdoc_test = (px_test, py_test, plantdoc_test_counts)

    classifier = SGDClassifier(
        loss="log_loss",
        alpha=0.0001,
        max_iter=30,
        tol=0.001,
        random_state=42,
        class_weight="balanced",
        n_jobs=1,
    )
    classifier.fit(X_train, y_train, sample_weight=dataset_weights)
    predictions = classifier.predict(X_test)
    classes = classifier.classes_.tolist()
    all_test_counts = dict(test_counts)
    if plantdoc_test:
        for label, count in plantdoc_test[2].items():
            all_test_counts[label] = all_test_counts.get(label, 0) + count
    metrics = {
        "dataset": "PlantVillage RGB color images" + (" + PlantDoc field images" if plantdoc_test else ""),
        "dataset_citation": "Mohanty, Hughes, and Salathé (2016), DOI: 10.3389/fpls.2016.01419",
        "license": "CC BY-SA 3.0",
        "train_images": int(len(y_train)),
        "test_images": int(len(y_test)),
        "classes": len(classes),
        "class_counts": {label: train_counts.get(label, 0) + all_test_counts.get(label, 0) for label in classes},
        "test_accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "test_macro_f1": round(float(f1_score(y_test, predictions, average="macro", zero_division=0)), 4),
        "plantvillage_test_images": int(len(y_test)),
        "split": "published PlantVillage leaf-grouped train/test split",
        "plantvillage_weighting": "PlantVillage and PlantDoc training examples receive equal aggregate sample weight." if plantdoc_test else "PlantVillage training examples receive equal sample weight.",
        "model": "32x32 HOG and RGB/HSV histograms with SGD logistic classifier",
        "caveat": "PlantVillage contains controlled-image samples. Test accuracy is not field-photo accuracy or a confirmed diagnosis.",
    }
    if plantdoc_test:
        px_test, py_test, plantdoc_test_counts = plantdoc_test
        plantdoc_predictions = classifier.predict(px_test)
        metrics.update({
            "plantdoc_citation": "PlantDoc dataset, https://github.com/pratikkayal/PlantDoc-Dataset",
            "plantdoc_license": "CC BY 4.0",
            "plantdoc_train_images": int(sum(plantdoc_train_counts.values())),
            "plantdoc_test_images": int(len(py_test)),
            "plantdoc_test_classes": len(plantdoc_test_counts),
            "plantdoc_classes_not_in_test": sorted(set(plantdoc_train_counts) - set(plantdoc_test_counts)),
            "plantdoc_class_counts": {
                label: plantdoc_train_counts.get(label, 0) + plantdoc_test_counts.get(label, 0)
                for label in sorted(set(plantdoc_train_counts) | set(plantdoc_test_counts))
            },
            "plantdoc_test_accuracy": round(float(accuracy_score(py_test, plantdoc_predictions)), 4),
            "plantdoc_test_macro_f1": round(float(f1_score(py_test, plantdoc_predictions, average="macro", zero_division=0)), 4),
            "plantdoc_split": "published PlantDoc train/test split; labels mapped to PlantVillage crop/disease names",
        })

    out = Path(args.output) if args.output else BACKEND / "ml" / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    kind = "plantvillage_plantdoc_hog_v1" if plantdoc_test else "plantvillage_hog_v1"
    joblib.dump({"kind": kind, "classifier": classifier}, out / "disease_model.joblib")
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
