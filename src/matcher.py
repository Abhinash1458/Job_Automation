"""Score how well a job fits the candidate profile (0-100).

Uses the LLM when available, but sends a COMPACT profile + short description to
stay well under free-tier token limits, and falls back to a local keyword
heuristic if the LLM errors (e.g. rate limit) so the daily list is never empty.
"""
from __future__ import annotations

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


def _compact_profile(profile: dict) -> str:
    return (
        f"Headline: {profile.get('headline','')}\n"
        f"Years experience: {profile.get('years_experience','')}\n"
        f"Skills: {', '.join(profile.get('skills', []))}\n"
        f"Preferred roles: {', '.join(profile.get('preferred_roles', []))}\n"
        f"Summary: {profile.get('summary','')[:500]}"
    )


def heuristic_score(profile: dict, job: dict) -> dict:
    """Cheap local fallback: skill/keyword overlap. No API call."""
    terms = [s.lower() for s in profile.get("skills", []) + profile.get("preferred_roles", [])]
    text = f"{job.get('title','')} {job.get('description','')}".lower()
    hits = sorted({t for t in terms if t and t in text})
    # these jobs already passed the GCC + AI-title filter, so start from a
    # relevant baseline and add for each matched skill.
    score = min(96, 74 + len(hits) * 4)
    verdict = "strong" if score >= 85 else "good" if score >= 70 else "weak"
    reasons = [f"Keyword match: {', '.join(hits[:6])}"] if hits else ["Title relevant to target roles"]
    return {"score": score, "verdict": verdict, "reasons": reasons, "missing": []}


def score_job(profile: dict, job: dict) -> dict:
    user = (
        "CANDIDATE:\n"
        f"{_compact_profile(profile)}\n\n"
        "JOB POSTING:\n"
        f"Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description:\n{job.get('description','')[:1800]}\n\n"
        "Score the fit."
    )
    try:
        return llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=700, effort="medium")
    except Exception as exc:  # noqa: BLE001 - rate limit / transient: fall back locally
        result = heuristic_score(profile, job)
        result["reasons"] = [f"(scored locally — LLM unavailable) {result['reasons'][0]}"]
        return result
