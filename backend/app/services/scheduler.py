"""Per-user scheduled daily match runs.

An in-app asyncio loop (started on FastAPI startup) wakes every
`scheduler_interval_minutes` and triggers a run for each Pro user whose opt-in
hour has arrived and who hasn't run yet today. No external cron/Celery-beat
needed for dev; in production the same `run_due_scheduled` can be called by a
cron/worker instead.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from ..config import settings
from ..database import SessionLocal
from ..models import MatchRun, Profile, User
from ..plans import get_plan
from . import pipeline
from .queue import enqueue_match_run


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def start_run_for_user(db, user: User) -> MatchRun | None:
    """Build + enqueue a match run for a user. Returns the run, or None if no profile."""
    profile_row = db.query(Profile).filter(Profile.user_id == user.id).one_or_none()
    if profile_row is None:
        return None
    profile = json.loads(profile_row.data or "{}")

    from src import config as src_config

    keywords = pipeline.default_keywords(profile)
    location = src_config.JOB_LOCATIONS[0]
    limit = src_config.MAX_JOBS_PER_RUN

    run = MatchRun(user_id=user.id, keywords=", ".join(keywords), location=location,
                   status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)
    enqueue_match_run(run.id, profile, keywords, location, limit, "gcc")
    return run


def run_due_scheduled() -> int:
    """Trigger runs for all users whose scheduled hour is due today. Returns count."""
    db = SessionLocal()
    triggered = 0
    try:
        now = datetime.now(timezone.utc)
        today = _today()
        users = db.query(User).filter(User.schedule_enabled.is_(True)).all()
        for user in users:
            if not get_plan(user.plan).scheduling:
                continue
            if user.last_scheduled_date == today:
                continue
            if now.hour < user.schedule_hour_utc:
                continue
            run = start_run_for_user(db, user)
            if run is not None:
                user.last_scheduled_date = today
                db.commit()
                triggered += 1
    finally:
        db.close()
    return triggered


async def scheduler_loop() -> None:
    interval = max(1, settings.scheduler_interval_minutes) * 60
    while True:
        try:
            n = run_due_scheduled()
            if n:
                print(f"[scheduler] triggered {n} scheduled run(s)")
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            print(f"[scheduler] error: {exc}")
        await asyncio.sleep(interval)
