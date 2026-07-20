"""Free job scraping via public job-board APIs (no key required).

Sources:
  - Remotive   https://remotive.com/api/remote-jobs   (remote roles, JSON)
  - Arbeitnow  https://www.arbeitnow.com/api/job-board-api (mixed, JSON)

NORMALIZED SHAPE (every scraper returns a list of these):
{
    "source":      str,   # "remotive" | "arbeitnow" | "apify"
    "title":       str,
    "company":     str,
    "location":    str,
    "url":         str,   # apply / listing URL
    "description": str,   # plain-ish text
    "posted":      str,   # date string, may be ""
}
"""
from __future__ import annotations

import html
import re

import requests

TIMEOUT = 30
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


def _matches(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def _remotive(keywords: list[str], limit: int) -> list[dict]:
    r = requests.get("https://remotive.com/api/remote-jobs", timeout=TIMEOUT,
                     params={"limit": 200})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        blob = f"{j.get('title','')} {j.get('category','')}"
        if not _matches(blob, keywords):
            continue
        out.append({
            "source": "remotive",
            "title": j.get("title", ""),
            "company": j.get("company_name", ""),
            "location": j.get("candidate_required_location", "Remote"),
            "url": j.get("url", ""),
            "description": _strip_html(j.get("description", "")),
            "posted": j.get("publication_date", ""),
        })
        if len(out) >= limit:
            break
    return out


def _arbeitnow(keywords: list[str], limit: int) -> list[dict]:
    r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("data", []):
        blob = f"{j.get('title','')} {' '.join(j.get('tags', []))}"
        if not _matches(blob, keywords):
            continue
        loc = j.get("location", "")
        if j.get("remote"):
            loc = f"{loc} (remote)".strip()
        out.append({
            "source": "arbeitnow",
            "title": j.get("title", ""),
            "company": j.get("company_name", ""),
            "location": loc,
            "url": j.get("url", ""),
            "description": _strip_html(j.get("description", "")),
            "posted": str(j.get("created_at", "")),
        })
        if len(out) >= limit:
            break
    return out


def scrape(keywords: list[str], location: str, limit: int) -> list[dict]:  # noqa: ARG001
    jobs: list[dict] = []
    for source in (_remotive, _arbeitnow):
        if len(jobs) >= limit:
            break
        try:
            jobs.extend(source(keywords, limit - len(jobs)))
        except Exception as exc:  # noqa: BLE001
            print(f"  free source {source.__name__} failed: {exc}")
    # de-dupe on url
    seen, deduped = set(), []
    for j in jobs:
        if j["url"] and j["url"] not in seen:
            seen.add(j["url"])
            deduped.append(j)
    return deduped[:limit]
