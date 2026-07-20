"""Find hints of a hiring team / hiring manager for a job.

Strategy (best-effort, no scraping of gated sites):
  1. Regex-extract any email addresses in the job description.
  2. Ask Claude to pull hiring-team hints (names, titles, emails, "apply via")
     that appear in the posting text.
Returns a contact dict; `has_contact` is True only when we found something
concrete enough to draft an outreach email to.
"""
from __future__ import annotations

import re

from . import llm

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "has_contact": {"type": "boolean"},
        "name": {"type": "string"},
        "title": {"type": "string"},
        "email": {"type": "string"},
        "notes": {"type": "string", "description": "where the hint came from"},
    },
    "required": ["has_contact", "name", "title", "email", "notes"],
}

_SYSTEM = (
    "You extract hiring-team contact hints from a job posting. Only report a "
    "name, title, or email that literally appears in the text. If the posting "
    "mentions a recruiter, hiring manager, or 'email your application to X', "
    "capture it. Never guess or fabricate an email address."
)


def find(job: dict) -> dict:
    description = job.get("description", "")
    emails = _EMAIL_RE.findall(description)

    result = llm.complete_json(
        _SYSTEM,
        f"Company: {job.get('company','')}\nTitle: {job.get('title','')}\n\n"
        f"Job posting text:\n{description[:6000]}\n\n"
        f"Emails already found by regex: {emails or 'none'}",
        _SCHEMA,
        max_tokens=800,
        effort="low",
    )

    # Trust the regex email if the model didn't surface one.
    if not result.get("email") and emails:
        result["email"] = emails[0]
        result["has_contact"] = True
        result["notes"] = (result.get("notes") or "") + " (email from posting text)"

    result["has_contact"] = bool(result.get("email") or result.get("name"))
    return result
