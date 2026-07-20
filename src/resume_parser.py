"""Turn a resume file (PDF/DOCX/TXT) into a structured profile.json.

The structured profile is the single source of truth that drives matching,
application filling, and email drafting.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, llm

# JSON schema Claude must fill from the resume text.
PROFILE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "full_name": {"type": "string"},
        "headline": {"type": "string", "description": "e.g. 'Backend Engineer, 3 yrs'"},
        "summary": {"type": "string"},
        "years_experience": {"type": "number"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "duration": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "company", "duration", "highlights"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "degree": {"type": "string"},
                    "institution": {"type": "string"},
                    "year": {"type": "string"},
                },
                "required": ["degree", "institution", "year"],
            },
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "preferred_roles": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "full_name", "headline", "summary", "years_experience", "skills",
        "experience", "education", "certifications", "preferred_roles",
    ],
}

_SYSTEM = (
    "You are a resume parser. Extract the candidate's details accurately from the "
    "resume text. Do not invent information; leave arrays empty and numbers 0 when "
    "the resume does not state something."
)


def _read_resume_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in (".docx", ".doc"):
        import docx

        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported resume format: {suffix} (use PDF, DOCX, or TXT)")


def find_resume() -> Path | None:
    """Return the first resume file dropped into data/resume/."""
    for pattern in ("*.pdf", "*.docx", "*.doc", "*.txt", "*.md"):
        files = sorted(config.RESUME_DIR.glob(pattern))
        if files:
            return files[0]
    return None


def parse(resume_path: Path | None = None) -> dict:
    """Parse the resume and write data/profile.json. Returns the profile dict."""
    resume_path = resume_path or find_resume()
    if resume_path is None:
        raise SystemExit(
            f"No resume found. Drop a PDF/DOCX/TXT into {config.RESUME_DIR} and re-run."
        )

    text = _read_resume_text(resume_path).strip()
    if not text:
        raise SystemExit(f"Could not extract text from {resume_path.name}.")

    profile = llm.complete_json(
        _SYSTEM,
        f"Resume text:\n\n{text}",
        PROFILE_SCHEMA,
        max_tokens=4000,
    )
    config.PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def load_profile() -> dict:
    if not config.PROFILE_PATH.exists():
        raise SystemExit("No profile.json yet. Run `python -m src.main parse` first.")
    return json.loads(config.PROFILE_PATH.read_text(encoding="utf-8"))
