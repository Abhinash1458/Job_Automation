"""Database models. Multi-user versions of what the CLI kept in profile.json + jobs.db."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Phase 3: subscription tier ---
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | pro
    plan_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Phase 3: per-user scheduled daily run ---
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_hour_utc: Mapped[int] = mapped_column(Integer, default=1)  # 0-23
    last_scheduled_date: Mapped[str] = mapped_column(String(10), default="")  # YYYY-MM-DD

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    runs: Mapped[list["MatchRun"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Payment(Base):
    """A Razorpay order/subscription payment attempt for a plan upgrade."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_code: Mapped[str] = mapped_column(String(20))
    order_id: Mapped[str] = mapped_column(String(120), default="")     # razorpay order id
    payment_id: Mapped[str] = mapped_column(String(120), default="")   # razorpay payment id
    amount_paise: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="created")  # created|paid|failed
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="payments")


class Profile(Base):
    """The parsed resume for a user (replaces the single global profile.json)."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    resume_path: Mapped[str] = mapped_column(String(1024), default="")
    data: Mapped[str] = mapped_column(Text, default="{}")  # JSON string of parsed profile
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class MatchRun(Base):
    """One background 'find + score jobs' job for a user."""

    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|error
    keywords: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    scored: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="runs")
    matches: Mapped[list["Match"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Match(Base):
    """A scored job for a user (multi-user version of a jobs.db row)."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(500), default="")
    company: Mapped[str] = mapped_column(String(300), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    source: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")  # posting text (for tailoring)
    score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(20), default="")
    reasons: Mapped[str] = mapped_column(Text, default="[]")   # JSON string
    missing: Mapped[str] = mapped_column(Text, default="[]")   # JSON string
    breakdown: Mapped[str] = mapped_column(Text, default="[]")  # JSON: match-engine factors
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|approved|applied|rejected
    # Tailored application packet (generated on demand via src/tailor.py).
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    pitch: Mapped[str] = mapped_column(Text, default="")
    answers: Mapped[str] = mapped_column(Text, default="[]")   # JSON: [{question, answer}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped["MatchRun"] = relationship(back_populates="matches")
