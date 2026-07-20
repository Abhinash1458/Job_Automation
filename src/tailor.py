"""Generate tailored application materials for a specific job using Claude:

  - a cover letter,
  - answers to common application questions,
  - a short, honest fit pitch used in outreach emails.
"""
from __future__ import annotations

import json

from . import config, llm

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "cover_letter": {"type": "string"},
        "pitch": {"type": "string", "description": "2-3 sentence why-I-fit summary"},
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
        },
    },
    "required": ["cover_letter", "pitch", "answers"],
}

_SYSTEM = (
    "You write concise, specific, honest job-application materials in the candidate's "
    "voice. Ground every claim in the candidate's real profile — never invent "
    "experience, employers, or numbers. Keep the cover letter under 250 words. "
    "Answer the common application questions using only facts from the profile."
)

# Common application questions we pre-answer so forms can be auto-filled.
_COMMON_QUESTIONS = [
    "Why are you interested in this role?",
    "What relevant experience do you have?",
    "What are your salary expectations?",
    "When can you start / what is your notice period?",
    "Are you authorized to work in this location / do you need sponsorship?",
]


def tailor(profile: dict, job: dict) -> dict:
    contact = config.applicant_contact()
    user = (
        "CANDIDATE PROFILE (JSON):\n"
        f"{json.dumps(profile, indent=2)}\n\n"
        "CANDIDATE CONTACT (for sign-off):\n"
        f"{json.dumps(contact, indent=2)}\n\n"
        "JOB POSTING:\n"
        f"Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description:\n{job.get('description','')[:6000]}\n\n"
        "Write a tailored cover letter, a 2-3 sentence fit pitch, and answer these "
        "application questions (leave salary/notice/authorization honest and flexible "
        "if the profile doesn't specify):\n- " + "\n- ".join(_COMMON_QUESTIONS)
    )
    return llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=3000)
