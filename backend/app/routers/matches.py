"""Job-matching endpoints: kick off a background run, poll it, read results."""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Match, MatchRun, Profile, User
from ..schemas import MatchDetail, MatchOut, MatchRunOut, RunRequest, SegmentOptions
from ..services import pipeline, usage
from ..services.queue import enqueue_match_run

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/options", response_model=SegmentOptions)
def segment_options():
    return SegmentOptions(company_types=pipeline.COMPANY_TYPES, job_types=pipeline.JOB_TYPES)

_ALLOWED_STATUS = {"new", "approved", "applied", "rejected"}


def _match_to_out(m: Match) -> MatchOut:
    return MatchOut(
        id=m.id, url=m.url, title=m.title, company=m.company, location=m.location,
        source=m.source, score=m.score, verdict=m.verdict,
        reasons=json.loads(m.reasons or "[]"), missing=json.loads(m.missing or "[]"),
        status=m.status,
    )


def _match_to_detail(m: Match) -> MatchDetail:
    return MatchDetail(
        id=m.id, url=m.url, title=m.title, company=m.company, location=m.location,
        source=m.source, score=m.score, verdict=m.verdict,
        reasons=json.loads(m.reasons or "[]"), missing=json.loads(m.missing or "[]"),
        status=m.status, description=m.description or "",
        breakdown=json.loads(m.breakdown or "[]"),
        cover_letter=m.cover_letter or "", pitch=m.pitch or "",
        answers=json.loads(m.answers or "[]"),
    )


def _owned(match_id: int, user: User, db: Session) -> Match:
    m = db.get(Match, match_id)
    if m is None or m.user_id != user.id:
        raise HTTPException(status_code=404, detail="Match not found")
    return m


@router.post("/run", response_model=MatchRunOut, status_code=202)
def start_run(
    req: RunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchRun:
    profile_row = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile_row is None:
        raise HTTPException(status_code=400, detail="Upload a CV first — no profile to match against.")
    usage.enforce_run_limit(db, user)  # 402 if over the plan's daily quota
    profile = json.loads(profile_row.data or "{}")

    from src import config as src_config  # local import; path set up in pipeline

    keywords = req.keywords or pipeline.default_keywords(profile)
    location = req.location or src_config.JOB_LOCATIONS[0]
    limit = req.limit or src_config.MAX_JOBS_PER_RUN

    run = MatchRun(user_id=user.id, keywords=", ".join(keywords), location=location, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    enqueue_match_run(run.id, profile, keywords, location, limit, req.company_type, req.job_type)
    return run


@router.get("", response_model=list[MatchOut])
def list_matches(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All of a user's matches across runs (for the tracker board)."""
    q = select(Match).where(Match.user_id == user.id)
    if status:
        q = q.where(Match.status == status)
    rows = db.scalars(q.order_by(Match.score.desc())).all()
    return [_match_to_out(m) for m in rows]


@router.get("/runs/latest", response_model=MatchRunOut | None)
def latest_run(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalar(
        select(MatchRun).where(MatchRun.user_id == user.id).order_by(MatchRun.id.desc())
    )


@router.get("/runs/{run_id}", response_model=MatchRunOut)
def get_run(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MatchRun:
    run = db.get(MatchRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/results", response_model=list[MatchOut])
def run_results(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.get(MatchRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = db.scalars(
        select(Match).where(Match.run_id == run_id).order_by(Match.score.desc())
    ).all()
    return [_match_to_out(m) for m in rows]


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _match_to_detail(_owned(match_id, user, db))


@router.post("/{match_id}/tailor", response_model=MatchDetail)
def tailor_match(match_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a tailored cover letter + answers for this job (on demand)."""
    if not pipeline.has_llm_key():
        raise HTTPException(status_code=503, detail="No LLM API key configured on the server.")
    usage.enforce_tailor_limit(db, user)  # 402 if over the plan's daily quota
    m = _owned(match_id, user, db)
    profile_row = db.scalar(select(Profile).where(Profile.user_id == user.id))
    profile = json.loads(profile_row.data if profile_row else "{}")
    contact = {
        "full_name": profile.get("full_name", user.full_name),
        "email": user.email,
    }
    job = {"title": m.title, "company": m.company, "location": m.location, "description": m.description}
    try:
        packet = pipeline.tailor_packet(profile, job, contact)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Tailoring failed: {exc}")
    m.cover_letter = packet.get("cover_letter", "")
    m.pitch = packet.get("pitch", "")
    m.answers = json.dumps(packet.get("answers", []))
    db.commit()
    db.refresh(m)
    return _match_to_detail(m)


@router.patch("/{match_id}", response_model=MatchOut)
def update_match(
    match_id: int,
    status: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchOut:
    if status not in _ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail=f"status must be one of {_ALLOWED_STATUS}")
    m = _owned(match_id, user, db)
    m.status = status
    db.commit()
    db.refresh(m)
    return _match_to_out(m)
