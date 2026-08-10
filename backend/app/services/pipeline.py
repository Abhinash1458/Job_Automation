"""Thin, multi-user-safe wrapper around the existing ``src/`` pipeline.

We do NOT reimplement business logic here. We import the project's proven
modules (resume parsing, scraping, scoring) and adapt them so each call is
stateless per user — the CLI kept one global ``profile.json`` and one SQLite
tracker; the SaaS keeps per-user rows in Postgres instead.
"""
from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

from ..config import PROJECT_ROOT

# Make the repo root importable so `import src...` resolves. The src modules
# load their own LLM/scraper keys from the project-root .env.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config as src_config  # noqa: E402
from src import gcc_directory, llm, resume_parser, tailor  # noqa: E402
from src.scrapers import company_scraper, workday  # noqa: E402

from . import match_engine  # noqa: E402


def parse_resume(resume_path: Path) -> dict:
    """Parse a single user's resume file into a structured profile dict.

    Reuses resume_parser's extraction + schema, but skips the module's global
    profile.json write so concurrent users never clobber each other.
    """
    text = resume_parser._read_resume_text(resume_path).strip()
    if not text:
        raise ValueError("Could not extract any text from the uploaded resume.")
    return llm.complete_json(
        resume_parser._SYSTEM,
        f"Resume text:\n\n{text}",
        resume_parser.PROFILE_SCHEMA,
        max_tokens=4000,
    )


# Job sources match against role TITLES, so search terms must be role titles
# (e.g. "AI Engineer"), never skill phrases ("RAG Pipelines") which never appear
# in a title. We derive titles from preferred_roles + the résumé headline.
_ROLE_WORD = re.compile(
    r"engineer|developer|scientist|analyst|architect|manager|lead|designer|"
    r"consultant|administrator|specialist|programmer",
    re.I,
)


def default_keywords(profile: dict) -> list[str]:
    """Role-title search terms for a user, derived robustly from their profile.

    Order: explicit preferred_roles, then role-like segments of the headline
    (e.g. 'AI Engineer | GenAI ...' -> 'AI Engineer'). Skill phrases are
    intentionally excluded because sources match against job titles. Falls back
    to the project's configured JOB_KEYWORDS only if nothing role-like is found.
    """
    candidates: list[str] = [r for r in profile.get("preferred_roles", []) if r]
    for seg in re.split(r"[|,/•\-–—]", profile.get("headline", "") or ""):
        seg = seg.strip()
        if seg and _ROLE_WORD.search(seg) and len(seg) <= 40:
            candidates.append(seg)

    seen: set[str] = set()
    roles: list[str] = []
    for r in candidates:
        key = r.lower()
        if key not in seen:
            seen.add(key)
            roles.append(r)

    return roles[:8] or src_config.JOB_KEYWORDS


# --- Segments: what kinds of employer + engagement a user can search ---
COMPANY_TYPES = ["any", "gcc", "product", "startup", "service"]
JOB_TYPES = ["any", "full_time", "contract", "remote"]

_CONTRACT_RE = re.compile(
    r"\b(contract|contractor|c2c|c2h|freelance|temporary|contract[-\s]?to[-\s]?hire)\b", re.I)


def _passes_company(company: str, company_type: str) -> bool:
    if company_type in ("", "any"):
        return True
    kind = match_engine.classify_company(company)
    if company_type == "gcc":
        return gcc_directory.is_gcc(company)
    if company_type == "service":
        return kind == "service"
    if company_type == "product":
        return kind in ("gcc", "product")
    if company_type == "startup":
        # independent product companies (not captive GCCs, not IT-services)
        return kind == "product" and not gcc_directory.is_gcc(company)
    return True


def _passes_job_type(job: dict, job_type: str) -> bool:
    if job_type in ("", "any"):
        return True
    text = f"{job.get('title','')} {job.get('description','')}"
    loc = (job.get("location") or "").lower()
    if job_type == "remote":
        return "remote" in loc or "remote" in text.lower()
    if job_type == "contract":
        return bool(_CONTRACT_RE.search(text))
    if job_type == "full_time":
        return not _CONTRACT_RE.search(text)
    return True


def source_jobs(keywords: list[str], location: str, company_type: str = "any") -> list[dict]:
    """Collect raw jobs across sources, then keep those matching the company type.

    GCC sourcing keeps Adzuna's built-in GCC filter; broader segments turn it off
    so startups / product / service employers can surface too.
    """
    raw: list[dict] = []
    for fn in (
        lambda: company_scraper.company_boards(keywords),
        lambda: workday.scrape(keywords),
        lambda: company_scraper.adzuna(keywords, [location], gcc_only=(company_type == "gcc")),
    ):
        try:
            raw += fn()
        except Exception:  # noqa: BLE001 - one source failing shouldn't kill the run
            pass
    return [j for j in raw if _passes_company(j.get("company", ""), company_type)]


def find_and_score(
    profile: dict,
    keywords: list[str],
    location: str,
    limit: int,
    on_progress: Callable[[int, int], None] | None = None,
    company_type: str = "any",
    job_type: str = "any",
) -> list[dict]:
    """Scrape jobs for the chosen segment, dedupe, and score with the match engine.

    Scoring is deterministic and explainable (no LLM), so every result carries a
    factor `breakdown`. `on_progress(scored, total)` fires after each score.
    """
    found = source_jobs(keywords, location, company_type)
    found = [j for j in found if _passes_job_type(j, job_type)]
    found = found[: max(limit * 2, limit)]

    seen: set[str] = set()
    jobs: list[dict] = []
    for j in found:
        url = j.get("url")
        if url and url not in seen:
            seen.add(url)
            jobs.append(j)

    results: list[dict] = []
    total = len(jobs)
    for i, job in enumerate(jobs, start=1):
        result = match_engine.score(profile, job, company_type)
        results.append({
            "url": job.get("url", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", "") or location,
            "source": job.get("source", ""),
            "description": job.get("description", "") or job.get("title", ""),
            "score": result["score"],
            "verdict": result["verdict"],
            "reasons": result["reasons"],
            "missing": result["missing"],
            "breakdown": result["breakdown"],
        })
        if on_progress:
            on_progress(i, total)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# Application questions we pre-answer (reused from the CLI tailor module).
_COMMON_QUESTIONS = tailor._COMMON_QUESTIONS


def tailor_packet(profile: dict, job: dict, contact: dict) -> dict:
    """Generate a tailored cover letter + pitch + answers for one job.

    Multi-user-safe: reuses tailor's prompt/schema but injects THIS user's
    contact (built from their profile) instead of the CLI's global .env contact.
    """
    import json as _json

    user = (
        "CANDIDATE PROFILE (JSON):\n"
        f"{_json.dumps(profile, indent=2)}\n\n"
        "CANDIDATE CONTACT (for sign-off):\n"
        f"{_json.dumps(contact, indent=2)}\n\n"
        "JOB POSTING:\n"
        f"Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description:\n{job.get('description','')[:6000]}\n\n"
        "Write a tailored cover letter, a 2-3 sentence fit pitch, and answer these "
        "application questions (leave salary/notice/authorization honest and flexible "
        "if the profile doesn't specify):\n- " + "\n- ".join(_COMMON_QUESTIONS)
    )
    return llm.complete_json(tailor._SYSTEM, user, tailor._SCHEMA, max_tokens=3000)


def has_llm_key() -> bool:
    return bool(src_config.LLM_API_KEY)
