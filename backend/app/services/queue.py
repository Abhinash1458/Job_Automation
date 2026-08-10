"""Background-job dispatch abstraction.

- If REDIS_URL is set, match runs are enqueued to an RQ worker (horizontally
  scalable — the real production path).
- Otherwise they run in a daemon thread in-process (zero-dependency dev path).

Both call the same `runner.run_match_job`, so behavior is identical.
"""
from __future__ import annotations

import threading

from ..config import settings
from .runner import run_match_job


def _redis_queue():
    """Return an RQ Queue if Redis is configured and libs are installed, else None."""
    if not settings.redis_url:
        return None
    try:
        from redis import Redis
        from rq import Queue
    except ImportError:
        return None
    return Queue("match_runs", connection=Redis.from_url(settings.redis_url))


def enqueue_match_run(
    run_id: int, profile: dict, keywords: list[str], location: str, limit: int,
    company_type: str = "any", job_type: str = "any",
) -> str:
    """Dispatch a match run. Returns the backend used ('rq' or 'thread')."""
    args = (run_id, profile, keywords, location, limit, company_type, job_type)
    q = _redis_queue()
    if q is not None:
        q.enqueue(run_match_job, *args, job_timeout=1800)
        return "rq"
    threading.Thread(target=run_match_job, args=args, daemon=True).start()
    return "thread"


def worker_backend() -> str:
    return "rq" if _redis_queue() is not None else "thread"
