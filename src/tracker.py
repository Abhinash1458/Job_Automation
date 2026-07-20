"""SQLite tracker: remembers every job we've seen so we never re-process or
double-apply, and records the tailored materials + outreach for your review.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    url          TEXT PRIMARY KEY,
    title        TEXT,
    company      TEXT,
    location     TEXT,
    source       TEXT,
    score        INTEGER,
    verdict      TEXT,
    status       TEXT,            -- seen | scored | for_review | approved | applied | rejected | skipped
    materials    TEXT,            -- JSON: cover letter, answers, pitch
    contact      TEXT,            -- JSON: hiring contact
    draft_path   TEXT,
    surfaced_date TEXT,           -- YYYY-MM-DD this job was surfaced in a daily run
    apply_state  TEXT,            -- '' | pending | assisted_opened | submitted | failed
    first_seen   TEXT,
    updated      TEXT
);
"""

# Columns added after the first release; applied idempotently for older DBs.
_MIGRATIONS = {
    "surfaced_date": "ALTER TABLE jobs ADD COLUMN surfaced_date TEXT",
    "apply_state": "ALTER TABLE jobs ADD COLUMN apply_state TEXT",
}


@contextmanager
def _conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
        for col, ddl in _MIGRATIONS.items():
            if col not in cols:
                conn.execute(ddl)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seen(url: str) -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone() is not None


def record_seen(job: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO jobs "
            "(url, title, company, location, source, status, first_seen, updated) "
            "VALUES (?,?,?,?,?, 'seen', ?, ?)",
            (job.get("url"), job.get("title"), job.get("company"), job.get("location"),
             job.get("source"), _now(), _now()),
        )


def update(url: str, **fields) -> None:
    if not fields:
        return
    for key in ("materials", "contact"):
        if key in fields and not isinstance(fields[key], str):
            fields[key] = json.dumps(fields[key])
    fields["updated"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE url = ?", (*fields.values(), url))


def stats() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}


def recent(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT title, company, score, verdict, status, draft_path, updated "
            "FROM jobs ORDER BY updated DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# --- Daily review / approve / apply workflow -------------------------------

def top_for_review(date: str, limit: int = 50) -> list[dict]:
    """Return the day's surfaced jobs, highest score first."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs WHERE surfaced_date = ? AND status = 'for_review' "
            "ORDER BY score DESC LIMIT ?", (date, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def approve(url: str) -> None:
    update(url, status="approved", apply_state="pending")


def reject(url: str) -> None:
    update(url, status="rejected")


def approved_pending() -> list[dict]:
    """Approved jobs not yet applied — the queue for assisted apply."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs WHERE status = 'approved' "
            "AND COALESCE(apply_state,'') != 'submitted' ORDER BY score DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def mark_apply_state(url: str, state: str) -> None:
    status = "applied" if state == "submitted" else None
    fields = {"apply_state": state}
    if status:
        fields["status"] = status
    update(url, **fields)
