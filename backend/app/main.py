import os, re, uuid, secrets, hashlib, hmac, io, asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
from pathlib import Path
import httpx
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import Base, engine, get_db, SessionLocal
from . import models as m, security as sec, services as svc, sms, ml_infer, yield_model
from .crops_data import CROPS, STAGES, find_crop

UPLOADS = Path(os.getenv("UPLOAD_DIR", "uploads")); UPLOADS.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    em, pw = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if em and pw:
        with SessionLocal() as db:
            if not db.scalar(select(m.Farmer).where(m.Farmer.email == em.lower())):
                db.add(m.Farmer(farmer_code="ADMIN", name="Administrator", email=em.lower(), password_hash=sec.hash_pw(pw),
                                role="admin", phone_verified=True)); db.commit()
    yield


app = FastAPI(title="Agriculture Threat Fusion API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(httpx.HTTPError)
async def _ext(_, e):
    return JSONResponse({"detail": f"An external data service is unavailable right now ({e.__class__.__name__}). Try again later."}, 502)


@app.exception_handler(svc.NotConfigured)
@app.exception_handler(sms.NotConfigured)
@app.exception_handler(ml_infer.ModelNotReady)
@app.exception_handler(yield_model.ModelNotReady)
async def _nc(_, e):
    return JSONResponse({"detail": str(e), "not_configured": True}, 503)


# ============================================================ helpers
PHONE_RE, EMAIL_RE = re.compile(r"^[6-9]\d{9}$"), re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    if len(d) == 12 and d.startswith("91"): d = d[2:]
    if len(d) == 11 and d.startswith("0"): d = d[1:]
    if not PHONE_RE.match(d): raise HTTPException(422, "Enter a valid 10-digit Indian mobile number.")
    return "+91" + d


def check_password(p: str):
    if len(p) < 8 or not re.search(r"[A-Za-z]", p) or not re.search(r"\d", p):
        raise HTTPException(422, "Password must be at least 8 characters with letters and numbers.")


def farmer_dict(f: m.Farmer):
    return {k: getattr(f, k) for k in ("id", "farmer_code", "name", "phone", "email", "role", "auth_provider", "phone_verified",
                                       "language", "state", "district", "taluk", "village")}


def token_resp(f: m.Farmer, remember=True):
    return {"token": sec.make_token(f.id, 30 if remember else 1), "farmer": farmer_dict(f),
            "needs_profile": not f.phone or not f.phone_verified}


async def create_otp(db: Session, target: str, purpose: str):
    last = db.scalar(select(m.Otp).where(m.Otp.target == target, m.Otp.purpose == purpose).order_by(m.Otp.created.desc()))
    if last and (datetime.utcnow() - last.created).total_seconds() < 30:
        raise HTTPException(429, "Please wait 30 seconds before requesting another OTP.")
    for o in db.scalars(select(m.Otp).where(m.Otp.target == target, m.Otp.purpose == purpose)): db.delete(o)
    code, salt = f"{secrets.randbelow(10 ** 6):06d}", secrets.token_hex(8)
    db.add(m.Otp(target=target, purpose=purpose, salt=salt, code_hash=hashlib.sha256((salt + code).encode()).hexdigest(),
                 expires=datetime.utcnow() + timedelta(minutes=5)))
    db.commit()
    await sms.send_sms(target, f"Agriculture Threat Fusion OTP: {code}. Valid for 5 minutes. Do not share it.")


def check_otp(db: Session, target: str, purpose: str, code: str):
    o = db.scalar(select(m.Otp).where(m.Otp.target == target, m.Otp.purpose == purpose).order_by(m.Otp.created.desc()))
    if not o or o.expires < datetime.utcnow(): raise HTTPException(400, "OTP expired or not requested. Request a new one.")
    if o.attempts >= 5: raise HTTPException(429, "Too many wrong attempts. Request a new OTP.")
    o.attempts += 1; db.commit()
    if not hmac.compare_digest(o.code_hash, hashlib.sha256((o.salt + code.strip()).encode()).hexdigest()):
        raise HTTPException(400, "Incorrect OTP.")
    db.delete(o); db.commit()


def find_farmer(db: Session, ident: str):
    ident = ident.strip()
    if "@" in ident: return db.scalar(select(m.Farmer).where(m.Farmer.email == ident.lower()))
    try: return db.scalar(select(m.Farmer).where(m.Farmer.phone == norm_phone(ident)))
    except HTTPException: return None


def save_record(db, user, kind, title, data, farm_id=None, crop=None):
    r = m.Record(farmer_id=user.id, farm_id=farm_id, kind=kind, title=title, data=data, crop=crop); db.add(r); db.commit(); return r


def get_farm(db: Session, user, farm_id: int) -> m.Farm:
    f = db.get(m.Farm, farm_id)
    if not f or f.farmer_id != user.id: raise HTTPException(404, "Farm not found")
    return f


def farm_dict(f: m.Farm):
    d = {c.name: getattr(f, c.name) for c in f.__table__.columns}; d["updated"] = f.updated.isoformat(); return d


def need_location(f: m.Farm):
    if f.lat is None or f.lon is None: raise HTTPException(422, "Select the farm location on the map first.")


# ============================================================ auth
class RegisterIn(BaseModel):
    name: str; phone: str; email: str; password: str; confirm: str


@app.post("/api/auth/register")
async def register(b: RegisterIn, db: Session = Depends(get_db)):
    if len(b.name.strip()) < 2: raise HTTPException(422, "Enter your full name.")
    phone = norm_phone(b.phone); email = b.email.strip().lower()
    if not EMAIL_RE.match(email): raise HTTPException(422, "Enter a valid email address.")
    check_password(b.password)
    if b.password != b.confirm: raise HTTPException(422, "Passwords do not match.")
    ex = db.scalar(select(m.Farmer).where((m.Farmer.phone == phone) | (m.Farmer.email == email)))
    if ex and ex.phone_verified: raise HTTPException(409, "Mobile number or email is already registered.")
    if ex:  # unverified earlier attempt - let them retry
        ex.name, ex.phone, ex.email, ex.password_hash = b.name.strip(), phone, email, sec.hash_pw(b.password)
    else:
        db.add(m.Farmer(farmer_code="F" + uuid.uuid4().hex[:8].upper(), name=b.name.strip(), phone=phone, email=email, password_hash=sec.hash_pw(b.password)))
    db.commit()
    await create_otp(db, phone, "register")
    return {"ok": True, "message": "OTP sent to your mobile number.", "phone": phone}


class OtpIn(BaseModel):
    phone: str; code: str = ""


@app.post("/api/auth/resend-otp")
async def resend(b: OtpIn, db: Session = Depends(get_db)):
    await create_otp(db, norm_phone(b.phone), "register"); return {"ok": True}


@app.post("/api/auth/verify-otp")
async def verify_register(b: OtpIn, db: Session = Depends(get_db)):
    phone = norm_phone(b.phone); check_otp(db, phone, "register", b.code)
    f = db.scalar(select(m.Farmer).where(m.Farmer.phone == phone))
    if not f: raise HTTPException(404, "Account not found")
    f.phone_verified = True; db.commit()
    return token_resp(f)


class LoginIn(BaseModel):
    identifier: str; password: str; remember: bool = True


@app.post("/api/auth/login")
async def login(b: LoginIn, db: Session = Depends(get_db)):
    key = b.identifier.strip().lower(); sec.lock_check(key)
    f = find_farmer(db, b.identifier)
    if not f or not sec.check_pw(b.password, f.password_hash):
        sec.lock_fail(key); raise HTTPException(401, "Incorrect phone/email or password.")
    if not f.is_active: raise HTTPException(403, "This account has been disabled.")
    if f.role == "farmer" and not f.phone_verified: raise HTTPException(403, "Mobile number not verified. Register again to receive a new OTP.")
    sec.lock_clear(key); return token_resp(f, b.remember)


@app.post("/api/auth/login-otp/request")
async def login_otp_req(b: OtpIn, db: Session = Depends(get_db)):
    phone = norm_phone(b.phone)
    if db.scalar(select(m.Farmer).where(m.Farmer.phone == phone, m.Farmer.phone_verified == True)):  # noqa: E712
        await create_otp(db, phone, "login")
    return {"ok": True, "message": "If this number is registered, an OTP has been sent."}


@app.post("/api/auth/login-otp/verify")
async def login_otp_verify(b: OtpIn, db: Session = Depends(get_db)):
    phone = norm_phone(b.phone); sec.lock_check("otp:" + phone)
    try: check_otp(db, phone, "login", b.code)
    except HTTPException: sec.lock_fail("otp:" + phone); raise
    f = db.scalar(select(m.Farmer).where(m.Farmer.phone == phone))
    if not f or not f.is_active: raise HTTPException(401, "Account not available")
    return token_resp(f)


class ForgotIn(BaseModel):
    identifier: str


@app.post("/api/auth/forgot")
async def forgot(b: ForgotIn, db: Session = Depends(get_db)):
    f = find_farmer(db, b.identifier)
    if f and f.phone and f.phone_verified: await create_otp(db, f.phone, "reset")
    return {"ok": True, "message": "If the account exists, an OTP has been sent to the registered mobile number."}


class ResetIn(BaseModel):
    identifier: str; code: str; new_password: str; confirm: str


@app.post("/api/auth/reset")
async def reset(b: ResetIn, db: Session = Depends(get_db)):
    check_password(b.new_password)
    if b.new_password != b.confirm: raise HTTPException(422, "Passwords do not match.")
    f = find_farmer(db, b.identifier)
    if not f or not f.phone: raise HTTPException(400, "Invalid request.")
    check_otp(db, f.phone, "reset", b.code)
    f.password_hash = sec.hash_pw(b.new_password); db.commit(); return {"ok": True}


class GoogleIn(BaseModel):
    id_token: str


@app.post("/api/auth/google")
async def google(b: GoogleIn, db: Session = Depends(get_db)):
    cid = os.getenv("GOOGLE_CLIENT_ID")
    if not cid: raise svc.NotConfigured("Google sign-in is not configured (set GOOGLE_CLIENT_ID).")
    from google.oauth2 import id_token
    from google.auth.transport import requests as greq
    try: info = await run_in_threadpool(id_token.verify_oauth2_token, b.id_token, greq.Request(), cid)
    except ValueError: raise HTTPException(401, "Google sign-in failed.")
    f = db.scalar(select(m.Farmer).where(m.Farmer.google_sub == info["sub"])) or \
        (db.scalar(select(m.Farmer).where(m.Farmer.email == info.get("email", "").lower())) if info.get("email_verified") else None)
    if f:
        f.google_sub = f.google_sub or info["sub"]
    else:
        f = m.Farmer(farmer_code="F" + uuid.uuid4().hex[:8].upper(), name=info.get("name", "Farmer"), email=info["email"].lower(),
                     auth_provider="google", google_sub=info["sub"]); db.add(f)
    db.commit()
    if not f.is_active: raise HTTPException(403, "This account has been disabled.")
    return token_resp(f)


# ============================================================ profile
@app.get("/api/me")
def me(u: m.Farmer = Depends(sec.current_user)): return farmer_dict(u)


class ProfileIn(BaseModel):
    name: str | None = None; email: str | None = None; language: str | None = None
    state: str | None = None; district: str | None = None; taluk: str | None = None; village: str | None = None


@app.put("/api/me")
def update_me(b: ProfileIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    d = b.model_dump(exclude_unset=True)
    if "email" in d and d["email"]:
        e = d["email"].strip().lower()
        if not EMAIL_RE.match(e): raise HTTPException(422, "Invalid email")
        if db.scalar(select(m.Farmer).where(m.Farmer.email == e, m.Farmer.id != u.id)): raise HTTPException(409, "Email already in use")
        d["email"] = e
    for k, v in d.items(): setattr(u, k, v)
    db.commit(); return farmer_dict(u)


class PwIn(BaseModel):
    old: str = ""; new: str


@app.post("/api/me/password")
def change_pw(b: PwIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    if u.password_hash and not sec.check_pw(b.old, u.password_hash): raise HTTPException(400, "Current password is incorrect.")
    check_password(b.new); u.password_hash = sec.hash_pw(b.new); db.commit(); return {"ok": True}


@app.post("/api/me/phone/request")
async def phone_req(b: OtpIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    p = norm_phone(b.phone)
    if db.scalar(select(m.Farmer).where(m.Farmer.phone == p, m.Farmer.id != u.id)): raise HTTPException(409, "Number already registered.")
    await create_otp(db, p, "phone"); return {"ok": True}


@app.post("/api/me/phone/verify")
async def phone_verify(b: OtpIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    p = norm_phone(b.phone); check_otp(db, p, "phone", b.code); u.phone, u.phone_verified = p, True; db.commit(); return farmer_dict(u)


# ============================================================ reference data
@app.get("/api/crops")
def crops(_: m.Farmer = Depends(sec.current_user)):
    return {"crops": [{"name": c["name"], "seasons": c["seasons"], "days": c["days"]} for c in CROPS], "stages": STAGES}


@app.get("/api/config")
def config(_: m.Farmer = Depends(sec.current_user)):
    e = os.getenv
    return {"supplier_url": e("SUPPLIER_URL", "https://share.google/tCbEJZtVxZKIURC8C"),
            "integrations": {"sms": bool(e("TWILIO_ACCOUNT_SID")), "google_login": bool(e("GOOGLE_CLIENT_ID")),
                             "market_prices": bool(e("DATA_GOV_API_KEY")), "satellite": bool(e("SENTINELHUB_CLIENT_ID")),
                             "disease_model": ml_infer.ready(), "yield_model": yield_model.ready(), "weather": True, "maps": True}}


@app.get("/api/geo/reverse")
async def rev(lat: float, lon: float, _: m.Farmer = Depends(sec.current_user)): return await svc.reverse_geocode(lat, lon)


@app.get("/api/geo/search")
async def geo_search(q: str, _: m.Farmer = Depends(sec.current_user)): return await svc.search_place(q)


@app.get("/api/weather")
async def weather(lat: float, lon: float, _: m.Farmer = Depends(sec.current_user)):
    w = await svc.get_weather(lat, lon); w["alerts"] = svc.weather_alerts(w); return w


# ============================================================ farms
@app.get("/api/farms")
def farms(u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    return [farm_dict(f) for f in db.scalars(select(m.Farm).where(m.Farm.farmer_id == u.id).order_by(m.Farm.id))]


class FarmIn(BaseModel):
    model_config = {"extra": "ignore"}
    name: str | None = None; crop: str | None = None; variety: str | None = None; stage: str | None = None; method: str | None = None
    prev_crop: str | None = None; season: str | None = None; start_date: str | None = None; harvest_date: str | None = None
    area: float | None = None; unit: str | None = None; soil: str | None = None; irrigation: str | None = None; water_source: str | None = None
    lat: float | None = None; lon: float | None = None; state: str | None = None; district: str | None = None; taluk: str | None = None
    village: str | None = None; soil_ph: float | None = None; soil_n: float | None = None; soil_p: float | None = None
    soil_k: float | None = None; soil_moisture: float | None = None; organic_carbon: float | None = None


def check_farm(d):
    if d.get("area") is not None and d["area"] <= 0: raise HTTPException(422, "Land area must be greater than 0.")
    if d.get("soil_ph") is not None and not 3 <= d["soil_ph"] <= 10: raise HTTPException(422, "Soil pH must be between 3 and 10.")
    if d.get("lat") is not None and not (6 <= d["lat"] <= 38 and 68 <= (d.get("lon") or 0) <= 98): raise HTTPException(422, "Location must be within India.")


@app.post("/api/farms")
def create_farm(b: FarmIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    d = b.model_dump(exclude_unset=True); check_farm(d)
    f = m.Farm(farmer_id=u.id, **d); db.add(f); db.commit()
    save_record(db, u, "crop", f"Crop & land saved: {f.crop or 'farm'}", farm_dict(f), f.id, f.crop)
    return farm_dict(f)


@app.put("/api/farms/{fid}")
def update_farm(fid: int, b: FarmIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); d = b.model_dump(exclude_unset=True); check_farm(d)
    for k, v in d.items(): setattr(f, k, v)
    db.commit(); save_record(db, u, "crop", f"Crop & land updated: {f.crop or 'farm'}", farm_dict(f), f.id, f.crop); return farm_dict(f)


@app.get("/api/farms/{fid}/analysis")
async def analysis(fid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); need_location(f); fd = farm_dict(f)
    w = await svc.get_weather(f.lat, f.lon); water = svc.water_requirement(fd, w)
    crop = find_crop(f.crop); alerts = svc.weather_alerts(w)
    suit = None
    if crop:
        mean_t = sum(((r["tmax"] or 0) + (r["tmin"] or 0)) / 2 for r in w["forecast"]) / 7
        s = svc._range_score(mean_t, crop["tabs_lo"], crop["topt_lo"], crop["topt_hi"], crop["tabs_hi"])
        suit = {"score": round(s * 100), "text": f"Forecast mean {mean_t:.1f} °C vs optimum {crop['topt_lo']}-{crop['topt_hi']} °C."}
    soil_ok = None
    if crop and f.soil: soil_ok = "Suitable" if svc.norm_soil(f.soil) in crop["soils"] else "Not among the best soils for this crop"
    out = {"growth_stage": f.stage, "weather_suitability": suit, "water": water, "soil_suitability": soil_ok,
           "disease_risk": [a for a in alerts if a["type"] == "fungal"] or "No weather-based fungal-disease signal in the next 7 days",
           "fertilizer": svc.soil_fertility(fd), "expected_harvest": f.harvest_date or (
               (date.fromisoformat(f.start_date) + timedelta(days=crop["days"])).isoformat() if crop and f.start_date else None),
           "threats": svc.build_threats(fd, w, water), "weather": w,
           "disclaimer": "Decision-support estimates, not guaranteed outcomes."}
    save_record(db, u, "analysis", f"Agricultural analysis: {f.crop}", {k: v for k, v in out.items() if k != "weather"}, f.id, f.crop)
    return out


# ============================================================ dashboard (each section fails independently)
async def safe(coro):
    try: return {"ok": True, "data": await coro}
    except Exception as e: return {"ok": False, "error": getattr(e, "detail", None) or str(e) or e.__class__.__name__}


@app.get("/api/farms/{fid}/dashboard")
async def dashboard(fid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); fd = farm_dict(f)
    if f.lat is None: return {"farm": fd, "needs_location": True}
    wres = await safe(svc.get_weather(f.lat, f.lon))
    w = wres["data"] if wres["ok"] else None
    sat = await safe(svc.ndvi_series(f.lat, f.lon))
    price = await safe(svc.market_prices(f.crop, f.state)) if f.crop else {"ok": False, "error": "No crop selected."}
    water = {"ok": True, "data": svc.water_requirement(fd, w)} if w else {"ok": False, "error": "Weather unavailable."}
    last = db.scalar(select(m.Record).where(m.Record.farmer_id == u.id, m.Record.kind == "disease").order_by(m.Record.created.desc()))
    ld = None
    if last: ld = {**last.data.get("result", {}), "date": last.created.date().isoformat()}
    threats = svc.build_threats(fd, w, water["data"] if water["ok"] else None, sat["data"] if sat["ok"] else None, ld)
    today = date.today().isoformat()
    for t in threats:
        if t["level"] in ("High", "Critical"):
            title = f"{t['level']}: {t['threat']}"
            if not db.scalar(select(m.Notification).where(m.Notification.farmer_id == u.id, m.Notification.title == title, func.date(m.Notification.created) == today)):
                db.add(m.Notification(farmer_id=u.id, title=title, body=t["evidence"], level=t["level"]))
    db.commit()
    return {"farm": fd, "weather": {**wres, "alerts": svc.weather_alerts(w)} if w else wres, "water": water, "satellite": sat, "price": price,
            "threats": threats, "fertility": svc.soil_fertility(fd), "disclaimer": "Threats are decision-support estimates, not guaranteed outcomes."}


# ============================================================ recommendation
class RecIn(BaseModel):
    lat: float; lon: float; soil: str | None = None; ph: float | None = None; state: str | None = None; district: str | None = None


@app.post("/api/recommend")
async def recommend(b: RecIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    clim = await svc.climate_history(b.lat, b.lon); r = svc.recommend_crops(clim, b.soil, b.ph)
    r["climate"] = clim; r["location"] = {"lat": b.lat, "lon": b.lon, "state": b.state, "district": b.district}
    save_record(db, u, "recommendation", f"Crop recommendation ({b.district or b.state or 'selected location'})", r); return r


# ============================================================ disease
@app.post("/api/disease")
async def disease(file: UploadFile = File(...), crop: str = Form(...), stage: str = Form(""), symptoms: str = Form(""),
                  variety: str = Form(""), observed: str = Form(""), farm_id: int | None = Form(None),
                  u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    if not ml_infer.ready(): raise ml_infer.ModelNotReady("Disease model is not trained yet. Run backend/ml/train_disease.py (see README).")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(415, "Please upload an image file.")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024: raise HTTPException(413, "Image too large (max 8 MB).")
    if farm_id: get_farm(db, u, farm_id)
    try: result = await run_in_threadpool(ml_infer.predict, data, crop)
    except ml_infer.ModelNotReady: raise
    except Exception: raise HTTPException(422, "Could not read this image. Upload a clear JPG/PNG photo.")
    d = UPLOADS / str(u.id); d.mkdir(parents=True, exist_ok=True); p = d / f"{uuid.uuid4().hex}.img"; p.write_bytes(data)
    rec = save_record(db, u, "disease", f"{crop}: {result['disease']}" + ("" if result["confident"] else " (uncertain)"),
                      {"result": result, "image": str(p), "crop": crop, "stage": stage, "symptoms": symptoms, "variety": variety, "observed": observed},
                      farm_id, crop)
    return {"id": rec.id, **result, "supplier_url": os.getenv("SUPPLIER_URL", "https://share.google/tCbEJZtVxZKIURC8C"),
            "supplier_note": "Supplier link is a configurable search link - suppliers are not verified and availability is not checked."}


@app.get("/api/files/{rid}")
def get_file(rid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    r = db.get(m.Record, rid)
    if not r or r.farmer_id != u.id or "image" not in r.data: raise HTTPException(404, "Not found")
    return FileResponse(r.data["image"], media_type="image/jpeg")


# ============================================================ yield
class YieldIn(BaseModel):
    farm_id: int


@app.post("/api/yield")
async def yield_(b: YieldIn, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, b.farm_id)
    missing = [n for n, v in (("crop", f.crop), ("land area", f.area), ("state", f.state)) if not v]
    if missing: raise HTTPException(422, "Missing saved details: " + ", ".join(missing) + ". Complete Crop and Land Information first.")
    c = find_crop(f.crop)
    r = await run_in_threadpool(yield_model.predict, farm_dict(f), c["days"] if c else None)
    factors = []
    ld = db.scalar(select(m.Record).where(m.Record.farmer_id == u.id, m.Record.kind == "disease").order_by(m.Record.created.desc()))
    if ld and ld.data["result"].get("confident") and not ld.data["result"].get("healthy"): factors.append({"effect": "reducing", "text": "A recent AI disease detection on this farm."})
    if f.irrigation == "Rainfed Farming": factors.append({"effect": "reducing", "text": "Rain-fed farming makes yield sensitive to dry spells."})
    if f.irrigation in ("Drip Irrigation", "Sprinkler Irrigation"): factors.append({"effect": "improving", "text": "Efficient irrigation method."})
    for n in svc.soil_fertility(farm_dict(f)):
        if n["rating"] == "Low": factors.append({"effect": "reducing", "text": f"Low soil {n['nutrient'].lower()} (farmer-entered test)."})
    r["qualitative_factors"] = factors
    save_record(db, u, "yield", f"Yield prediction: {f.crop}", r, f.id, f.crop); return r


@app.get("/api/farms/{fid}/markets")
async def markets(fid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); need_location(f); return await svc.nearby_markets(f.lat, f.lon)


@app.get("/api/prices")
async def prices(crop: str, state: str | None = None, district: str | None = None, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    r = await svc.market_prices(crop, state, district); save_record(db, u, "price", f"Market prices: {crop}", r, crop=crop); return r


@app.get("/api/farms/{fid}/satellite")
async def satellite(fid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); need_location(f); r = await svc.ndvi_series(f.lat, f.lon)
    save_record(db, u, "satellite", "Satellite NDVI check", r, f.id, f.crop); return r


@app.get("/api/farms/{fid}/threats")
async def threats(fid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    f = get_farm(db, u, fid); need_location(f); fd = farm_dict(f)
    w = await svc.get_weather(f.lat, f.lon); water = svc.water_requirement(fd, w)
    sat = (await safe(svc.ndvi_series(f.lat, f.lon)))
    t = svc.build_threats(fd, w, water, sat["data"] if sat["ok"] else None)
    save_record(db, u, "threat", f"Threat analysis ({len(t)} items)", {"threats": t}, f.id, f.crop)
    return {"threats": t, "satellite_note": None if sat["ok"] else sat["error"], "disclaimer": "Decision-support estimates, not guaranteed outcomes."}


# ============================================================ notifications / history / reports
@app.get("/api/notifications")
def notifs(u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(m.Notification).where(m.Notification.farmer_id == u.id).order_by(m.Notification.created.desc()).limit(50)).all()
    return [{"id": n.id, "title": n.title, "body": n.body, "level": n.level, "read": n.read, "created": n.created.isoformat()} for n in rows]


@app.post("/api/notifications/read")
def notifs_read(u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(m.Notification).where(m.Notification.farmer_id == u.id, m.Notification.read == False)): n.read = True  # noqa: E712
    db.commit(); return {"ok": True}


def rec_dict(r, full=False):
    d = {"id": r.id, "kind": r.kind, "crop": r.crop, "title": r.title, "created": r.created.isoformat(), "farm_id": r.farm_id}
    if full: d["data"] = {k: v for k, v in r.data.items() if k != "image"}; d["has_image"] = "image" in r.data
    return d


@app.get("/api/history")
def history(kind: str | None = None, crop: str | None = None, start: str | None = None, end: str | None = None,
            u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    q = select(m.Record).where(m.Record.farmer_id == u.id)
    if kind: q = q.where(m.Record.kind == kind)
    if crop: q = q.where(m.Record.crop == crop)
    if start: q = q.where(m.Record.created >= datetime.fromisoformat(start))
    if end: q = q.where(m.Record.created < datetime.fromisoformat(end) + timedelta(days=1))
    return [rec_dict(r) for r in db.scalars(q.order_by(m.Record.created.desc()).limit(300))]


@app.get("/api/history/{rid}")
def history_one(rid: int, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    r = db.get(m.Record, rid)
    if not r or r.farmer_id != u.id: raise HTTPException(404, "Record not found")
    return rec_dict(r, True)


@app.get("/api/reports/pdf")
def report(kind: str, u: m.Farmer = Depends(sec.current_user), db: Session = Depends(get_db)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from xml.sax.saxutils import escape
    rows = db.scalars(select(m.Record).where(m.Record.farmer_id == u.id, m.Record.kind == kind).order_by(m.Record.created.desc()).limit(50)).all()
    buf = io.BytesIO(); st = getSampleStyleSheet()
    el = [Paragraph("Agriculture Threat Fusion - " + kind.title() + " report", st["Title"]),
          Paragraph(f"Farmer: {escape(u.name)} ({u.farmer_code}) - generated {datetime.now():%d %b %Y %H:%M}", st["Normal"]), Spacer(1, 12)]
    if not rows: el.append(Paragraph("No records yet.", st["Normal"]))
    for r in rows:
        el.append(Paragraph(f"<b>{escape(r.title)}</b> - {r.created:%d %b %Y}", st["Heading4"]))
        txt = escape(str({k: v for k, v in r.data.items() if k != "image"}))[:1500]
        el.append(Paragraph(txt, st["BodyText"])); el.append(Spacer(1, 6))
    el.append(Paragraph("<i>All figures are decision-support estimates, not guaranteed outcomes.</i>", st["Normal"]))
    SimpleDocTemplate(buf, pagesize=A4).build(el); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={kind}-report.pdf"})


# ============================================================ admin
@app.get("/api/admin/stats")
def a_stats(_: m.Farmer = Depends(sec.admin_user), db: Session = Depends(get_db)):
    kinds = dict(db.execute(select(m.Record.kind, func.count()).group_by(m.Record.kind)).all())
    return {"farmers": db.scalar(select(func.count()).select_from(m.Farmer).where(m.Farmer.role == "farmer")),
            "farms": db.scalar(select(func.count()).select_from(m.Farm)), "records_by_kind": kinds,
            "models": {"disease": ml_infer.model_info(), "yield": yield_model.info()}}


@app.get("/api/admin/farmers")
def a_farmers(_: m.Farmer = Depends(sec.admin_user), db: Session = Depends(get_db)):
    return [{**farmer_dict(f), "is_active": f.is_active, "created": f.created.isoformat()} for f in db.scalars(select(m.Farmer).order_by(m.Farmer.id.desc()).limit(500))]


@app.post("/api/admin/farmers/{fid}/toggle")
def a_toggle(fid: int, a: m.Farmer = Depends(sec.admin_user), db: Session = Depends(get_db)):
    f = db.get(m.Farmer, fid)
    if not f or f.id == a.id: raise HTTPException(400, "Cannot change this account")
    f.is_active = not f.is_active; db.commit(); return {"is_active": f.is_active}


@app.get("/api/admin/activity")
def a_activity(_: m.Farmer = Depends(sec.admin_user), db: Session = Depends(get_db)):
    return [{"id": r.id, "farmer_id": r.farmer_id, "kind": r.kind, "title": r.title, "created": r.created.isoformat()}
            for r in db.scalars(select(m.Record).order_by(m.Record.created.desc()).limit(100))]


@app.get("/api/admin/integrations")
def a_integrations(a: m.Farmer = Depends(sec.admin_user)): return config(a)["integrations"]


@app.get("/api/health")
def health(): return {"ok": True}
