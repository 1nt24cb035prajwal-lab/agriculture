"""Train the crop-disease classifier (MobileNetV2 transfer learning).

Dataset: PlantVillage (folders named like  Tomato___Late_blight/ ... ), e.g.
  kaggle datasets download -d abdallahalidev/plantvillage-dataset   ->  use the 'color' folder
Run:  python ml/train_disease.py --data /path/to/plantvillage/color --epochs 8 --finetune 8
Output: ml/artifacts/{disease_model.keras, classes.json, metrics.json, confusion_matrix.csv}
"""
import argparse, json
from pathlib import Path
import numpy as np
import tensorflow as tf

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--epochs", type=int, default=8)
ap.add_argument("--finetune", type=int, default=8)
ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--img", type=int, default=224)
a = ap.parse_args()
out = Path(__file__).parent / "artifacts"; out.mkdir(exist_ok=True)
S = (a.img, a.img)

# 70% train / 15% val / 15% test (test never used for training or model selection)
train = tf.keras.utils.image_dataset_from_directory(a.data, validation_split=.3, subset="training", seed=42, image_size=S, batch_size=a.batch)
rest = tf.keras.utils.image_dataset_from_directory(a.data, validation_split=.3, subset="validation", seed=42, image_size=S, batch_size=a.batch, shuffle=False)
classes = train.class_names
n = int(rest.cardinality()); val, test = rest.take(n // 2), rest.skip(n // 2)
print(f"{len(classes)} classes | batches train={int(train.cardinality())} val={n // 2} test={n - n // 2}")
AUTO = tf.data.AUTOTUNE
train, val, test = [d.prefetch(AUTO) for d in (train.shuffle(1000), val, test)]

aug = tf.keras.Sequential([tf.keras.layers.RandomFlip("horizontal_and_vertical"), tf.keras.layers.RandomRotation(.15),
                           tf.keras.layers.RandomZoom(.15), tf.keras.layers.RandomContrast(.15), tf.keras.layers.RandomBrightness(.15)])
base = tf.keras.applications.MobileNetV2(input_shape=S + (3,), include_top=False, weights="imagenet")
base.trainable = False
inp = tf.keras.Input(S + (3,))
x = aug(inp)
x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1)(x)          # MobileNetV2 preprocessing (inside the model)
x = base(x, training=False)
x = tf.keras.layers.GlobalAveragePooling2D()(x)
x = tf.keras.layers.Dropout(.3)(x)
model = tf.keras.Model(inp, tf.keras.layers.Dense(len(classes), activation="softmax")(x))
cb = [tf.keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True, monitor="val_accuracy"),
      tf.keras.callbacks.ReduceLROnPlateau(patience=1, factor=.3)]

model.compile(tf.keras.optimizers.Adam(1e-3), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(train, validation_data=val, epochs=a.epochs, callbacks=cb)
base.trainable = True
for l in base.layers[:-40]: l.trainable = False                  # fine-tune top layers only
model.compile(tf.keras.optimizers.Adam(1e-5), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(train, validation_data=val, epochs=a.finetune, callbacks=cb)

y_true = np.concatenate([y.numpy() for _, y in test]); y_pred = np.concatenate([model.predict(x, verbose=0).argmax(1) for x, _ in test])
acc = float((y_true == y_pred).mean())
from sklearn.metrics import classification_report, confusion_matrix
rep = classification_report(y_true, y_pred, labels=range(len(classes)), target_names=classes, output_dict=True, zero_division=0)
np.savetxt(out / "confusion_matrix.csv", confusion_matrix(y_true, y_pred, labels=range(len(classes))), fmt="%d", delimiter=",")
model.save(out / "disease_model.keras")
(out / "classes.json").write_text(json.dumps(classes, indent=1))
m = {"test_accuracy": round(acc, 4), "test_images": int(len(y_true)), "macro_f1": round(rep["macro avg"]["f1-score"], 4),
     "classes": len(classes), "dataset": Path(a.data).as_posix(),
     "caveat": "Measured on a random split of a lab-style dataset. Field accuracy with phone photos is usually lower - test on field images."}
(out / "metrics.json").write_text(json.dumps(m, indent=1))
print(json.dumps(m, indent=1))
print("TARGET >=95%:", "REACHED" if acc >= .95 else "NOT reached - train longer, unfreeze more layers, or add more data/augmentation.")
