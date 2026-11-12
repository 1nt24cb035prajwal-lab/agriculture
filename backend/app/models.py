from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.utcnow()


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="local")
    google_sub: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(10), default="farmer")  # farmer | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(5), default="en")
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    taluk: Mapped[str | None] = mapped_column(String(80), nullable=True)
    village: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime, default=now)


class Otp(Base):
    __tablename__ = "otps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(200), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    salt: Mapped[str] = mapped_column(String(32))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[datetime] = mapped_column(DateTime, default=now)


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), default="My Farm")
    crop: Mapped[str | None] = mapped_column(String(80), nullable=True)
    variety: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prev_crop: Mapped[str | None] = mapped_column(String(80), nullable=True)
    season: Mapped[str | None] = mapped_column(String(30), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    harvest_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(10), default="acres")
    soil: Mapped[str | None] = mapped_column(String(30), nullable=True)
    irrigation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    water_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    taluk: Mapped[str | None] = mapped_column(String(80), nullable=True)
    village: Mapped[str | None] = mapped_column(String(80), nullable=True)
    soil_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_n: Mapped[float | None] = mapped_column(Float, nullable=True)   # available N kg/ha
    soil_p: Mapped[float | None] = mapped_column(Float, nullable=True)   # available P kg/ha
    soil_k: Mapped[float | None] = mapped_column(Float, nullable=True)   # available K kg/ha
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_carbon: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


FARM_FIELDS = [c.name for c in Farm.__table__.columns if c.name not in ("id", "farmer_id", "updated")]


class Record(Base):
    """Generic per-farmer activity table: kind = disease | recommendation | water | yield |
    threat | weather | satellite | analysis | price."""
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), index=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    crop: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(10), default="Medium")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[datetime] = mapped_column(DateTime, default=now)
