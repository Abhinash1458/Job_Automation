"""Read LinkedIn (and similar) job-alert emails from your Gmail inbox and turn
them into job dicts — so the roles LinkedIn already emails you become a source.

Activates only when GMAIL_ADDRESS + GMAIL_APP_PASSWORD are set in .env
(a Google App Password: https://myaccount.google.com/apppasswords).

Returns the normalized shape documented in free_scraper.py.
"""
from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header

from bs4 import BeautifulSoup

from .. import config

# LinkedIn job-alert senders and lookalikes.
_SENDERS = ("jobalerts-noreply@linkedin.com", "jobs-noreply@linkedin.com",
            "jobs-listings@linkedin.com", "linkedin.com")
_VIEW_RE = re.compile(r"https?://[^\s\"']*?/jobs/view/\d+[^\s\"']*")


def _decode(value: str) -> str:
    parts = decode_header(value or "")
    return "".join(
        (b.decode(enc or "utf-8", "ignore") if isinstance(b, bytes) else b)
        for b, enc in parts
    )


def _clean_url(url: str) -> str:
    return url.split("?")[0].replace("/comm/", "/")


def _parse_linkedin_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, dict] = {}
    for a in soup.find_all("a", href=_VIEW_RE):
        url = _clean_url(a["href"])
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        # company/location usually sit in the text just after the title anchor
        tail = ""
        parent = a.find_parent(["td", "div", "tr"])
        if parent:
            tail = parent.get_text(" · ", strip=True)
        company = ""
        m = re.search(re.escape(title) + r"\s*·?\s*([A-Z][\w&.,'\- ]{2,40})", tail)
        if m:
            company = m.group(1).strip(" ·")
        jobs.setdefault(url, {
            "source": "linkedin-email", "title": title, "company": company,
            "location": "", "url": url, "description": tail[:800], "posted": "",
        })
    return list(jobs.values())


def scrape(days: int = 2, limit: int = 100) -> list[dict]:
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        return []
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    except Exception as exc:  # noqa: BLE001
        print(f"  email source: login failed ({exc})")
        return []

    jobs: list[dict] = []
    try:
        imap.select("INBOX")
        from datetime import datetime, timedelta
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        # OR across known senders
        for sender in _SENDERS:
            typ, data = imap.search(None, f'(SINCE {since} FROM "{sender}")')
            if typ != "OK":
                continue
            for num in data[0].split()[-30:]:
                _, msg_data = imap.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                html = _extract_html(msg)
                if html:
                    jobs.extend(_parse_linkedin_html(html))
                if len(jobs) >= limit:
                    break
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass

    # de-dupe on url
    seen, out = set(), []
    for j in jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            out.append(j)
    return out[:limit]


def _extract_html(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "ignore")
        return ""
    if msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True)
        return payload.decode(msg.get_content_charset() or "utf-8", "ignore") if payload else ""
    return ""
