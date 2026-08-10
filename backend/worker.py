"""RQ worker entrypoint for background match runs.

Run alongside the API when REDIS_URL is set:
    python worker.py
It consumes the 'match_runs' queue and executes runner.run_match_job.
"""
from __future__ import annotations

from redis import Redis
from rq import Queue, Worker

from app.config import settings


def main() -> None:
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is not set — no queue to consume.")
    conn = Redis.from_url(settings.redis_url)
    q = Queue("match_runs", connection=conn)
    Worker([q], connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
