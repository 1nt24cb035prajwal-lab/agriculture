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

## 2. Train the disease model (target ≥ 95 %)

```bash
pip install -r backend/requirements-ml.txt
pip install kaggle        # then put your kaggle.json in ~/.kaggle
kaggle datasets download -d abdallahalidev/plantvillage-dataset -p data --unzip
cd backend
python ml/train_disease.py --data data/plantvillage\ dataset/color --epochs 8 --finetune 8
```
Use a GPU (Google Colab / Kaggle notebook) – CPU training takes hours. The script uses MobileNetV2 transfer learning, a 70/15/15 train/val/test split, prints **test accuracy** and writes `ml/artifacts/metrics.json`. It says whether the 95 % target was reached – **the number is only known after you run it**; PlantVillage normally gives 95–99 %.
⚠ Honest caveat: PlantVillage is lab-style imagery with near-duplicate photos, so test accuracy overstates real-field accuracy. The app therefore rejects low-confidence results (`DISEASE_MIN_CONFIDENCE`, default 0.80) instead of guessing.

## 3. Train the yield model

Download a real crop-production CSV (e.g. Kaggle “Crop Production in India”, columns `State_Name, District_Name, Crop_Year, Season, Crop, Area, Production`) into `backend/data/`, then:
```bash
python ml/train_yield.py --csv data/crop_production.csv
```
It reports hold-out R²/MAE (shown in the UI). Regional averages come from the same dataset.

## 4. API keys (all optional – each feature explains itself if missing)

| Feature | Variable | Where |
|---|---|---|
| SMS OTP | `TWILIO_*` | twilio.com |
| Google login | `GOOGLE_CLIENT_ID` (backend) + `VITE_GOOGLE_CLIENT_ID` (frontend/.env) | Google Cloud Console |
| Market prices | `DATA_GOV_API_KEY` | data.gov.in (Agmarknet) |
| Satellite NDVI | `SENTINELHUB_CLIENT_ID/SECRET` | Sentinel Hub dashboard |
| Weather, maps, geocoding, nearby markets | none needed | Open-Meteo, OpenStreetMap |

Admin login: the `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`, then open **/app/admin**.

## 5. What is real, what is limited

**Working (real logic):** registration with password (production phone OTP has expiry, attempt limit, and resend throttle; skipped in development), login by phone/email, forgot/reset password, Google sign-in (when configured), JWT sessions, login lockout, per-farmer data isolation, crop & land forms, full-screen map picker with reverse geocoding, live weather + alerts, FAO-56 water requirement, rule-based crop recommendation with explained scores, threat fusion engine, notifications, activity history, PDF reports, profile editing, admin panel, market prices & nearby markets, NDVI.

**Needs you to supply something:** trained disease model, yield dataset/model, API keys above. Until then those pages show a clear “not configured” message – no fake values are generated.

**Known limits (be aware):**
- Crop recommendation uses a generic agronomic reference table (`app/crops_data.py`) + 12-month climate – not a trained ML model, no soil database, no satellite input. Edit the table to match your region.
- Disease severity is *not* estimated (classifier only gives type + confidence). Treatment text is generic, with no dosages, and always defers to KVK/agri officer.
- Yield model uses historical district data (state/district/crop/season/area/year); this season’s weather/NDVI/disease are shown as qualitative factors only.
- Nearby “markets” come from OpenStreetMap, not an official mandi register. Agmarknet prices are the latest published, not tick-live.
- Satellite page shows NDVI time-series, not image tiles.
- Database uses one generic `records` table for history instead of 19 separate tables; farm data is in `farms`.
- UI translations cover navigation labels only (en/kn/hi); extend `frontend/src/i18n.js`.
- Email OTP/recovery and SMS/email alert delivery are not implemented (in-app notifications only).
- Login lockout is in-memory (use Redis for multi-worker deployments). Use HTTPS in production.
- This code was syntax-checked but **not run end-to-end** in the build environment (no internet to install packages). Expect to fix small issues on first run.
