"""Score how well a job fits the candidate profile (0-100) using Claude."""
from __future__ import annotations

import json

from . import llm

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "integer", "description": "0-100 fit score"},
        "verdict": {"type": "string", "enum": ["strong", "good", "weak", "skip"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"},
                    "description": "requirements the candidate does not clearly meet"},
    },
    "required": ["score", "verdict", "reasons", "missing"],
}

_SYSTEM = (
    "You are a pragmatic technical recruiter. Score how well a candidate fits a job "
    "on a 0-100 scale, weighing required skills, seniority, and role relevance. "
    "Be realistic: a perfect keyword match with wrong seniority is not a strong fit."
)


def score_job(profile: dict, job: dict) -> dict:
    user = (
        "CANDIDATE PROFILE (JSON):\n"
        f"{json.dumps(profile, indent=2)}\n\n"
        "JOB POSTING:\n"
        f"Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description:\n{job.get('description','')[:6000]}\n\n"
        "Score the fit."
    )
    return llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=1500, effort="medium")
