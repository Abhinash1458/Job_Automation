"""CV upload + parsed-profile endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Profile, User
from ..schemas import ProfileOut
from ..services import pipeline

router = APIRouter(prefix="/profile", tags=["profile"])

_ALLOWED = {".pdf", ".docx", ".doc", ".txt", ".md"}


def _to_out(p: Profile) -> ProfileOut:
    return ProfileOut(
        resume_filename=p.resume_filename,
        updated_at=p.updated_at,
        data=json.loads(p.data or "{}"),
    )


@router.get("", response_model=ProfileOut | None)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    return _to_out(p) if p else None


@router.post("/upload", response_model=ProfileOut)
async def upload_cv(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    if not pipeline.has_llm_key():
        raise HTTPException(status_code=503, detail="No LLM API key configured on the server.")

    name = file.filename or "resume"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext not in _ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use PDF, DOCX, or TXT.")

    user_dir = settings.upload_path / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"resume{ext}"
    dest.write_bytes(await file.read())

    try:
        parsed = pipeline.parse_resume(dest)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not parse resume: {exc}")

    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if p is None:
        p = Profile(user_id=user.id)
        db.add(p)
    p.resume_filename = name
    p.resume_path = str(dest)
    p.data = json.dumps(parsed)
    db.commit()
    db.refresh(p)
    return _to_out(p)
