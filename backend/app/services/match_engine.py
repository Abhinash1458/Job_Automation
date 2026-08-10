"""Transparent, deterministic match engine.

Scores a job against a candidate profile as a weighted blend of explainable
factors — no LLM required (so it works regardless of API quota, and every score
comes with a breakdown the UI can show). The optional LLM scorer can still layer
on top later; this is the dependable floor.

Factors (weights sum to 1.0):
  skills 0.34 · role 0.24 · seniority 0.20 · location 0.08 · recency 0.05 · company_fit 0.09
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

from ..config import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src import gcc_directory  # noqa: E402

# --- skill synonyms so "k8s" matches "kubernetes", etc. ---
_SYNONYMS: dict[str, list[str]] = {
    "kubernetes": ["k8s"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "large language models": ["llm", "llms"],
    "natural language processing": ["nlp"],
    "javascript": ["js"],
    "typescript": ["ts"],
    "postgresql": ["postgres", "psql"],
    "amazon web services": ["aws"],
    "google cloud": ["gcp"],
    "continuous integration": ["ci/cd", "cicd", "ci cd"],
    "react": ["reactjs", "react.js"],
    "node": ["nodejs", "node.js"],
    "retrieval augmented generation": ["rag"],
}

_SENIOR = re.compile(r"\b(senior|sr\.?|lead|staff|principal|architect)\b", re.I)
_VERY_SENIOR = re.compile(r"\b(staff|principal|director|vp|vice\s*president|head\s+of|chief|distinguished|fellow)\b", re.I)
_JUNIOR = re.compile(r"\b(junior|jr\.?|intern|graduate|entry[-\s]?level|associate|trainee)\b", re.I)
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs|yr)\b", re.I)
_WORD = re.compile(r"[a-z0-9+#.]+", re.I)

WEIGHTS = {
    "skills": 0.34, "role": 0.24, "seniority": 0.20,
    "location": 0.08, "recency": 0.05, "company_fit": 0.09,
}


def _clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "")}


def _skill_present(skill: str, text_low: str, toks: set[str]) -> bool:
    s = skill.lower().strip()
    if not s:
        return False
    if " " in s or "/" in s:
        return s in text_low  # multi-word: substring
    if s in toks:
        return True
    for canon, alts in _SYNONYMS.items():
        group = {canon, *alts}
        if s in group and (any(a in text_low for a in group) or bool(group & toks)):
            return True
    return False


def _score_skills(profile: dict, title: str, desc: str) -> tuple[int, str, list[str]]:
    skills = [s for s in profile.get("skills", []) if s]
    if not skills:
        return 60, "no skills listed on profile", []
    text_low = f"{title} {desc}".lower()
    toks = _tokens(f"{title} {desc}")
    key = skills[:12]
    matched = [s for s in key if _skill_present(s, text_low, toks)]
    missing = [s for s in key if s not in matched]
    ratio = len(matched) / max(1, len(key))
    score = _clamp(45 + ratio * 60)  # floor so a couple of hits still reads "fair"
    detail = f"matched {len(matched)}/{len(key)} key skills"
    return score, detail, missing[:5]


def _role_words(profile: dict) -> set[str]:
    roles = list(profile.get("preferred_roles", []))
    roles.append(profile.get("headline", ""))
    return {w.lower() for r in roles for w in _WORD.findall(r) if len(w) > 2}


def _score_role(profile: dict, title: str) -> tuple[int, str]:
    rw = _role_words(profile)
    tw = _tokens(title)
    if not rw or not tw:
        return 55, "role relevance unclear"
    overlap = rw & tw
    domain = {"ai", "ml", "genai", "llm", "data", "backend", "software", "engineer",
              "developer", "scientist", "analyst"}
    score = 40 + len(overlap) * 14 + (12 if overlap & domain else 0)
    return _clamp(score), f"title shares {len(overlap)} term(s) with your target roles"


def _required_years(title: str, desc: str) -> float | None:
    m = _YEARS.search(desc or "")
    if m:
        return float(m.group(1))
    if _VERY_SENIOR.search(title):
        return 9.0
    if _SENIOR.search(title):
        return 6.0
    if _JUNIOR.search(title):
        return 1.0
    return None


def _score_seniority(profile: dict, title: str, desc: str) -> tuple[int, str, str | None]:
    cand = float(profile.get("years_experience", 0) or 0)
    req = _required_years(title, desc)
    if req is None:
        return 78, "seniority not specified — assumed mid-level", None
    gap = abs(cand - req)
    if cand < req:
        score = _clamp(100 - (req - cand) * 14)  # under-qualified penalized harder
        note = f"role suggests ~{req:.0f} yrs; you have {cand:.0f}" if gap >= 2 else None
    else:
        score = _clamp(100 - (cand - req) * 8)   # over-qualified penalized lightly
        note = None
    detail = f"needs ~{req:.0f} yrs, you have {cand:.0f} yrs"
    return score, detail, note


_CITY = ("bengaluru", "bangalore", "hyderabad", "secunderabad")


def _score_location(profile: dict, job_loc: str, target: str) -> tuple[int, str]:
    loc = (job_loc or "").lower()
    if "remote" in loc:
        return 100, "remote"
    if any(c in loc for c in _CITY) or (target and target.lower() in loc):
        return 100, "in your target city"
    if "india" in loc:
        return 75, "elsewhere in India"
    return 55, "location differs from target"


def _score_recency(posted: str) -> tuple[int, str]:
    if not posted:
        return 70, ""
    m = re.search(r"(\d+)\s*day", posted, re.I)
    if "today" in posted.lower() or "hour" in posted.lower():
        return 100, "posted today"
    if m:
        d = int(m.group(1))
        return (_clamp(100 - d * 2), f"posted {d}d ago")
    try:
        dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        d = (datetime.now(timezone.utc) - dt).days
        return _clamp(100 - max(0, d) * 2), f"posted {max(0, d)}d ago"
    except ValueError:
        return 70, ""


# --- company-type classification (drives the company_fit factor + segments) ---
_SERVICE = gcc_directory._SERVICES_BLOCKLIST


def classify_company(company: str) -> str:
    c = (company or "").lower()
    if not c:
        return "unknown"
    if any(b in c for b in _SERVICE):
        return "service"
    if gcc_directory.is_gcc(company):
        return "gcc"
    return "product"  # default bucket for a recognizable employer with a real board


def _score_company_fit(company: str, want: str) -> tuple[int, str]:
    kind = classify_company(company)
    if not want or want == "any":
        return 85, f"{kind} company"
    if want == kind:
        return 100, f"matches your {want} preference"
    # product ⊇ startup-ish; be lenient across product/startup
    if {want, kind} <= {"product", "startup"}:
        return 80, f"{kind} company"
    return 60, f"{kind} company (you chose {want})"


def score(profile: dict, job: dict, company_type: str = "any") -> dict:
    title = job.get("title", "")
    desc = job.get("description", "") or title
    s_skills, d_skills, missing = _score_skills(profile, title, desc)
    s_role, d_role = _score_role(profile, title)
    s_sen, d_sen, sen_note = _score_seniority(profile, title, desc)
    s_loc, d_loc = _score_location(profile, job.get("location", ""), job.get("search_location", ""))
    s_rec, d_rec = _score_recency(job.get("posted", ""))
    s_co, d_co = _score_company_fit(job.get("company", ""), company_type)

    factors = [
        ("Skills", s_skills, WEIGHTS["skills"], d_skills),
        ("Role relevance", s_role, WEIGHTS["role"], d_role),
        ("Seniority fit", s_sen, WEIGHTS["seniority"], d_sen),
        ("Location", s_loc, WEIGHTS["location"], d_loc),
        ("Recency", s_rec, WEIGHTS["recency"], d_rec),
        ("Company fit", s_co, WEIGHTS["company_fit"], d_co),
    ]
    total = _clamp(sum(sc * w for _, sc, w, _ in factors))
    verdict = "strong" if total >= 85 else "good" if total >= 70 else "fair" if total >= 55 else "weak"

    # Reasons: the two strongest factors, phrased for a person.
    ranked = sorted(factors, key=lambda f: f[1] * f[2], reverse=True)
    reasons = [f"{name}: {detail}" for name, sc, w, detail in ranked[:3] if detail]
    if sen_note:
        missing = [sen_note, *missing]

    return {
        "score": total,
        "verdict": verdict,
        "reasons": reasons,
        "missing": missing[:5],
        "breakdown": [
            {"factor": name, "score": sc, "weight": round(w, 2), "detail": detail}
            for name, sc, w, detail in factors
        ],
    }
