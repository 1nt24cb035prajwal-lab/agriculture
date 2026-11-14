# 🌾 Agriculture Threat Fusion

Full-stack smart-agriculture platform: **FastAPI + SQLite/PostgreSQL** backend, **React + Vite + Leaflet + Recharts** frontend, **TensorFlow** disease model and **scikit-learn** yield model.

## 1. Run locally

### Windows

Install Python 3.12 and Node.js LTS, then run:

```bat
setup-local.bat
run-local.bat
```

The setup script installs backend and frontend dependencies and copies
`backend\.env.example` to `backend\.env` if needed. The run script starts both
servers and opens http://localhost:5173. For Node.js, you can use
`winget install --id OpenJS.NodeJS.LTS --exact`.

### Linux or macOS

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd frontend && npm install && cd ..
./run-dev.sh
```

The frontend is at http://localhost:5173 and the API is at
http://localhost:8000. Optional: copy a farm photo to
`frontend/public/field.jpg` for the background (a green gradient is used
otherwise).

In `APP_ENV=dev`, new accounts can register and log in without phone OTP verification. Other OTPs are **printed in the backend console** (no SMS needed to test). In production set `APP_ENV=prod` and the `TWILIO_*` variables; phone verification is required during registration.

## 2. Train and test the disease model

PlantVillage contains 14 crop species and 38 crop/disease classes; it is not limited to three crops. Use its published, leaf-grouped split in this layout:

```text
backend/data/plant_disease/
  train/<Crop___Disease>/*.jpg
  test/<Crop___Disease>/*.jpg
```

Then run:

```bash
python backend/ml/train_disease.py --data backend/data/plant_disease
```

For an additional field-photo dataset, download [PlantDoc](https://github.com/pratikkayal/PlantDoc-Dataset) (the published mirror has 2,578 images from 13 species; [Hugging Face mirror and split](https://huggingface.co/datasets/agyaatcoder/PlantDoc)). Extract its `train/` and `test/` class folders, then train on both:

```bash
python backend/ml/train_disease.py --data backend/data/plant_disease --plantdoc-data path/to/PlantDoc
```

The trainer maps PlantDoc's 28 folder labels to the matching PlantVillage crop/disease labels and gives the two training datasets equal aggregate sample weight. It evaluates the resulting classifier separately on each dataset's published test split. In the local run (45,938 training images), the combined classifier scored 60.99% accuracy / 0.5094 macro-F1 on 10,709 PlantVillage test images and 13.56% / 0.1046 macro-F1 on 236 PlantDoc test images (27 classes). A PlantDoc-only training experiment scored 16.10% / 0.1275 on that same PlantDoc split. These low field-photo results do not support claiming reliable field detection; keep the combined candidate separate from the checked-in PlantVillage model using `--output path/to/artifacts` until field performance is improved and independently validated. PlantVillage is controlled-image research data; neither test score is field diagnostic accuracy or a confirmed diagnosis. PlantVillage declares [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); PlantDoc declares [CC BY 4.0](https://github.com/pratikkayal/PlantDoc-Dataset/blob/main/LICENSE.txt). Verify the combined model's redistribution terms before publishing the trained bundle, and retain required attribution.

## 3. Train the crop recommendation model

Provide a crop recommendation CSV with columns `N,P,K,temperature,humidity,ph,rainfall,label` at `backend/data/crop_recommendation.csv`, then run:

```bash
python backend/ml/train_crop.py --csv backend/data/crop_recommendation.csv
```

The benchmark CSV used for the local training run is the [Crop Recommendation dataset](https://huggingface.co/datasets/liaad/agricultural-data), mirrored from Kaggle. Its redistribution terms have not been verified, so the CSV and resulting crop model remain local and are excluded from Git. Use only a dataset whose license permits model training and distribution. The script reports stratified 80/20 held-out accuracy and macro-F1, then saves the model under `backend/ml/artifacts/`. The recommender uses it only when soil N/P/K test values are entered; temperature and rainfall come from the selected location's climate data, and humidity comes from Open-Meteo. The app retains the separate, explainable agronomic-range scores as well.

## 4. Train the yield model

Download the [Crop Production in India dataset](https://www.kaggle.com/datasets/abhinand05/crop-production-in-india) (columns `State_Name, District_Name, Crop_Year, Season, Crop, Area, Production`) into `backend/data/`, then:
```bash
python backend/ml/train_yield.py --csv backend/data/crop_production.csv
```
It holds out the latest complete years for testing, reports R²/MAE/RMSE, and refits the serving model on valid historical rows. The local training run (1997–2010 train, 2011–2014 test) scored R² 0.876, MAE 1.11 t/ha, and RMSE 3.536 t/ha. Districts outside the 254 most common training districts use an `OTHER` category. The dataset mirror's redistribution license is unverified, so the CSV and trained model remain local; do not publish them without reviewing the original dataset terms.

## 5. API keys (all optional – each feature explains itself if missing)

| Feature | Variable | Where |
|---|---|---|
| SMS OTP | `TWILIO_*` | twilio.com |
| Google login | `GOOGLE_CLIENT_ID` (backend) + `VITE_GOOGLE_CLIENT_ID` (frontend/.env) | Google Cloud Console |
| Market prices | `DATA_GOV_API_KEY` | data.gov.in (Agmarknet) |
| Satellite NDVI | `SENTINELHUB_CLIENT_ID/SECRET` | Sentinel Hub dashboard |
| Weather, maps, geocoding, nearby markets | none needed | Open-Meteo, OpenStreetMap |

Admin login: the `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`, then open **/app/admin**.

## 6. What is real, what is limited

**Working (real logic):** registration with password (production phone OTP has expiry, attempt limit, and resend throttle; skipped in development), login by phone/email, forgot/reset password, Google sign-in (when configured), JWT sessions, login lockout, per-farmer data isolation, crop & land forms, full-screen map picker with reverse geocoding, live weather + alerts, FAO-56 water requirement, rule-based crop recommendation with explained scores, threat fusion engine, notifications, activity history, PDF reports, profile editing, admin panel, market prices & nearby markets, NDVI.

**Needs you to supply something:** a yield dataset/model and any API keys above. The PlantVillage disease model is included; optional crop recommendation and yield models can be trained locally. Unconfigured features show a clear message – no fake values are generated.

**Known limits (be aware):**
- Crop recommendations include transparent agronomic-range scores; optional dataset-based crop suitability scores require soil N/P/K test values and a locally trained model. Neither is field-validated.
- Disease severity is *not* estimated (classifier only gives type + confidence). Treatment text is generic, with no dosages, and always defers to KVK/agri officer.
- Yield model uses historical district data (state/district/crop/season/area/year); this season’s weather/NDVI/disease are shown as qualitative factors only.
- Nearby “markets” come from OpenStreetMap, not an official mandi register. Agmarknet prices are the latest published, not tick-live.
- Satellite page shows NDVI time-series, not image tiles.
- Database uses one generic `records` table for history instead of 19 separate tables; farm data is in `farms`.
- UI translations cover navigation labels only (en/kn/hi); extend `frontend/src/i18n.js`.
- Email OTP/recovery and SMS/email alert delivery are not implemented (in-app notifications only).
- Login lockout is in-memory (use Redis for multi-worker deployments). Use HTTPS in production.
- This code was syntax-checked but **not run end-to-end** in the build environment (no internet to install packages). Expect to fix small issues on first run.
