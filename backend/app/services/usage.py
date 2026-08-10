"""Usage accounting + plan-limit enforcement (per UTC day)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Match, MatchRun, User
from ..plans import Plan, get_plan


def _day_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def runs_today(db: Session, user_id: int) -> int:
    start, _ = _day_bounds()
    return db.scalar(
        select(func.count(MatchRun.id)).where(
            MatchRun.user_id == user_id, MatchRun.created_at >= start
        )
    ) or 0


def tailors_today(db: Session, user_id: int) -> int:
    """Packets generated today = matches whose cover_letter was written today.

    We approximate by counting matches with a non-empty packet created for the
    user's runs today. Simpler + good enough: count matches updated with a
    cover letter today via the run's created_at is unreliable, so we count
    matches with a packet among today's runs.
    """
    start, _ = _day_bounds()
    # matches with a packet belonging to runs started today
    return db.scalar(
        select(func.count(Match.id))
        .join(MatchRun, Match.run_id == MatchRun.id)
        .where(
            Match.user_id == user_id,
            Match.cover_letter != "",
            MatchRun.created_at >= start,
        )
    ) or 0


def usage_summary(db: Session, user: User) -> dict:
    plan = get_plan(user.plan)
    return {
        "plan": plan.code,
        "plan_name": plan.name,
        "runs_used": runs_today(db, user.id),
        "runs_limit": plan.runs_per_day,
        "tailors_used": tailors_today(db, user.id),
        "tailors_limit": plan.tailors_per_day,
        "scheduling": plan.scheduling,
    }


def _over(used: int, limit: int) -> bool:
    return limit != -1 and used >= limit


def enforce_run_limit(db: Session, user: User) -> None:
    plan = get_plan(user.plan)
    if _over(runs_today(db, user.id), plan.runs_per_day):
        raise HTTPException(
            status_code=402,
            detail=f"Daily match-run limit reached ({plan.runs_per_day}/day on {plan.name}). "
                   f"Upgrade to Pro for more.",
        )


def enforce_tailor_limit(db: Session, user: User) -> None:
    plan = get_plan(user.plan)
    if _over(tailors_today(db, user.id), plan.tailors_per_day):
        raise HTTPException(
            status_code=402,
            detail=f"Daily tailored-packet limit reached ({plan.tailors_per_day}/day on {plan.name}). "
                   f"Upgrade to Pro for more.",
        )


def require_scheduling(plan_code: str | None) -> Plan:
    plan = get_plan(plan_code)
    if not plan.scheduling:
        raise HTTPException(
            status_code=402,
            detail="Scheduled daily runs are a Pro feature. Upgrade to enable them.",
        )
    return plan
