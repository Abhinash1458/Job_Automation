"""Draft outreach emails to hiring contacts.

Per your setting, this is DRAFT-ONLY: it never sends. Each draft is written as
a .eml file to data/drafts/ (open in any mail client), and optionally pushed to
your Gmail "Drafts" folder if GMAIL_APP_PASSWORD is set — you review and hit send.
"""
from __future__ import annotations

import re
import time
from email.message import EmailMessage
from pathlib import Path

from . import config, llm

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
}

_SYSTEM = (
    "You write short, warm, professional cold outreach emails to a hiring "
    "contact about a specific role. 120-160 words. Reference one concrete, "
    "relevant strength from the candidate's pitch. Polite, not pushy. Sign off "
    "with the candidate's name and contact details. No fabricated claims."
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")[:40] or "job"


def compose(profile: dict, job: dict, contact: dict, pitch: str) -> dict:
    c = config.applicant_contact()
    user = (
        f"Candidate: {c['full_name']} | {c['email']} | {c['phone']}\n"
        f"Links: {c['linkedin']} {c['portfolio']} {c['github']}\n"
        f"Candidate pitch: {pitch}\n"
        f"Headline: {profile.get('headline','')}\n\n"
        f"Role: {job.get('title','')} at {job.get('company','')}\n"
        f"Job link: {job.get('url','')}\n\n"
        f"Hiring contact: {contact.get('name') or 'Hiring Team'} "
        f"({contact.get('title','')})\n\n"
        "Write the outreach email."
    )
    return llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=1200, effort="medium")


def save_draft(job: dict, contact: dict, subject: str, body: str) -> Path:
    """Write an .eml draft to disk and optionally push to Gmail Drafts."""
    msg = EmailMessage()
    msg["From"] = config.GMAIL_ADDRESS or config.EMAIL
    msg["To"] = contact.get("email") or ""
    msg["Subject"] = subject
    msg.set_content(body)

    fname = f"{int(time.time())}_{_slug(job.get('company',''))}_{_slug(job.get('title',''))}.eml"
    path = config.DRAFTS_DIR / fname
    path.write_bytes(bytes(msg))

    if config.GMAIL_APP_PASSWORD and config.GMAIL_ADDRESS:
        try:
            _push_to_gmail_drafts(msg)
        except Exception as exc:  # noqa: BLE001
            print(f"  (Gmail draft push failed: {exc}; .eml saved locally)")

    return path


def _push_to_gmail_drafts(msg: EmailMessage) -> None:
    import imaplib

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    imap.append('"[Gmail]/Drafts"', "\\Draft", imaplib.Time2Internaldate(time.time()),
                bytes(msg))
    imap.logout()
