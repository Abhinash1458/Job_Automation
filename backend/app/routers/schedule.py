"""Per-user scheduled-run preferences (a Pro feature)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..plans import get_plan
from ..schemas import MatchRunOut, ScheduleOut, ScheduleUpdate
from ..services import scheduler, usage

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _to_out(user: User) -> ScheduleOut:
    return ScheduleOut(
        enabled=user.schedule_enabled,
        hour_utc=user.schedule_hour_utc,
        last_run_date=user.last_scheduled_date or "",
        scheduling_allowed=get_plan(user.plan).scheduling,
    )


@router.get("", response_model=ScheduleOut)
def get_schedule(user: User = Depends(get_current_user)):
    return _to_out(user)


@router.put("", response_model=ScheduleOut)
def update_schedule(req: ScheduleUpdate, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if req.enabled:
        usage.require_scheduling(user.plan)  # 402 for Free
    user.schedule_enabled = req.enabled
    user.schedule_hour_utc = req.hour_utc
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.post("/run-now", response_model=MatchRunOut)
def run_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Manually trigger the scheduled pipeline immediately (Pro)."""
    usage.require_scheduling(user.plan)
    usage.enforce_run_limit(db, user)
    run = scheduler.start_run_for_user(db, user)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Upload a CV first.")
    return run
