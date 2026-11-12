import os, time, secrets, jwt, bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .db import get_db
from . import models as m

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    SECRET = secrets.token_hex(32)
    print("WARNING: JWT_SECRET not set - using a random one (logins reset on restart).")
bearer = HTTPBearer(auto_error=False)


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(p: str, h: str | None) -> bool:
    try:
        return bool(h) and bcrypt.checkpw(p.encode()[:72], h.encode())
    except ValueError:
        return False


def make_token(farmer_id: int, days: int = 7) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode({"sub": str(farmer_id), "exp": exp}, SECRET, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> m.Farmer:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = int(jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired - please log in again")
    u = db.get(m.Farmer, uid)
    if not u or not u.is_active:
        raise HTTPException(401, "Account not available")
    return u


def admin_user(u: m.Farmer = Depends(current_user)) -> m.Farmer:
    if u.role != "admin":
        raise HTTPException(403, "Admin access required")
    return u


# --- login attempt protection (in-memory; use Redis if you run several workers) ---
_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 15 * 60


def lock_check(key: str):
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < WINDOW]
    if len(_fails[key]) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")


def lock_fail(key: str):
    _fails.setdefault(key, []).append(time.time())


def lock_clear(key: str):
    _fails.pop(key, None)
