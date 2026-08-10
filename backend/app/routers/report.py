"""Career report — derived entirely from the user's own profile + match data.

All scoring logic and copy here is original: a simple, transparent readiness
model (experience depth, skill breadth, certifications, live-market fit) rather
than any third-party product's methodology or wording.
"""
from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Match, Profile, User
from ..schemas import CareerReport, ReportSkillBar

router = APIRouter(prefix="/report", tags=["report"])


def _clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def _label(readiness: int) -> str:
    if readiness >= 75:
        return "Strong — ready to apply broadly"
    if readiness >= 55:
        return "Competitive — target well-matched roles"
    if readiness >= 35:
        return "Developing — close a few gaps first"
    return "Early — build depth before applying widely"


@router.get("", response_model=CareerReport)
def career_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CareerReport:
    profile_row = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile_row is None:
        raise HTTPException(status_code=400, detail="Upload a CV first to generate a report.")
    p = json.loads(profile_row.data or "{}")

    years = float(p.get("years_experience", 0) or 0)
    skills = [s for s in p.get("skills", []) if s]
    certs = [c for c in p.get("certifications", []) if c]

    matches = db.scalars(select(Match).where(Match.user_id == user.id)).all()
    scores = [m.score for m in matches]
    avg_score = _clamp(sum(scores) / len(scores)) if scores else 0
    strong = sum(1 for s in scores if s >= 85)

    # Four transparent readiness dimensions (0-100 each).
    exp_bar = _clamp(years * 18)
    skill_bar = _clamp(len(skills) * 7)
    cert_bar = _clamp(len(certs) * 25)
    market_bar = avg_score
    bars = [
        ReportSkillBar(label="Experience depth", value=exp_bar),
        ReportSkillBar(label="Skill breadth", value=skill_bar),
        ReportSkillBar(label="Certifications", value=cert_bar),
        ReportSkillBar(label="Live-market fit", value=market_bar),
    ]
    readiness = _clamp(0.30 * exp_bar + 0.25 * skill_bar + 0.15 * cert_bar + 0.30 * market_bar)

    # Aggregate the gaps flagged across scored jobs.
    gap_counter: Counter[str] = Counter()
    for m in matches:
        for g in json.loads(m.missing or "[]"):
            gap_counter[g] += 1
    focus = [g for g, _ in gap_counter.most_common(6)]

    company_counter = Counter(m.company for m in matches if m.company)
    top_companies = [c for c, _ in company_counter.most_common(6)]

    return CareerReport(
        headline=p.get("headline", "") or p.get("full_name", "Your profile"),
        years_experience=years,
        readiness=readiness,
        readiness_label=_label(readiness),
        strengths=skills[:8],
        focus_areas=focus,
        target_roles=[r for r in p.get("preferred_roles", []) if r][:6],
        skill_bars=bars,
        matches_analyzed=len(matches),
        strong_matches=strong,
        avg_score=avg_score,
        top_companies=top_companies,
    )
