"""Backend settings, loaded from backend/.env (falls back to sane defaults)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent      # .../backend
PROJECT_ROOT = BACKEND_DIR.parent                         # repo root (has src/)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./jobhunt.db"
    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"

    # --- Phase 3 ---
    # Worker queue. If set, background match runs go to an RQ/Redis worker;
    # otherwise they run in an in-process thread (fine for local/dev).
    redis_url: str = ""

    # Billing (Razorpay, India-first). If keys are absent the billing flow runs
    # in MOCK mode: it issues a fake order and upgrades on confirm, so the whole
    # tier/limit system is testable end-to-end without a live gateway.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Per-user scheduled daily runs. The in-app scheduler wakes every
    # scheduler_interval_minutes and triggers any user whose opt-in hour is due.
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 15

    @property
    def billing_mock(self) -> bool:
        """True when no live Razorpay keys are configured."""
        return not (self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = (BACKEND_DIR / self.upload_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
