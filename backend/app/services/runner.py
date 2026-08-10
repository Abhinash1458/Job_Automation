"""Background execution of a match run.

Phase 1 uses FastAPI BackgroundTasks (in-process) so the scaffold runs with no
Redis/Celery. The function owns its OWN DB session — never reuse the request's.
Swap the call site for an RQ/Celery task in Phase 3 for horizontal scaling.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..database import SessionLocal
from ..models import Match, MatchRun
from . import pipeline


def run_match_job(
    run_id: int, profile: dict, keywords: list[str], location: str, limit: int,
    company_type: str = "any", job_type: str = "any",
) -> None:
    db = SessionLocal()
    try:
        run = db.get(MatchRun, run_id)
        if run is None:
            return
        run.status = "running"
        db.commit()

        def on_progress(scored: int, total: int) -> None:
            run.total = total
            run.scored = scored
            db.commit()

        results = pipeline.find_and_score(
            profile, keywords, location, limit, on_progress, company_type, job_type)

        for r in results:
            db.add(Match(
                run_id=run.id,
                user_id=run.user_id,
                url=r["url"],
                title=r["title"],
                company=r["company"],
                location=r["location"],
                source=r["source"],
                description=r.get("description", ""),
                score=r["score"],
                verdict=r["verdict"],
                reasons=json.dumps(r["reasons"]),
                missing=json.dumps(r["missing"]),
                breakdown=json.dumps(r.get("breakdown", [])),
            ))
        run.total = len(results)
        run.scored = len(results)
        run.status = "done"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - record failure, don't crash the worker
        db.rollback()
        run = db.get(MatchRun, run_id)
        if run is not None:
            run.status = "error"
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
