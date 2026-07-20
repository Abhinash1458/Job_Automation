"""Workday scraper — for big GCCs/banks that use Workday (no free ATS API, but
Workday exposes a hidden JSON search endpoint, so NO browser/Playwright needed).

Workday tenant/site names aren't in any directory, so we keep a curated,
verified seed in data/workday_tenants.json:
    {"Company": {"tenant": "...", "dc": "wd1", "site": "..."}, ...}
Add more companies there over time (find the URL like
https://{tenant}.{dc}.myworkdayjobs.com/{site} on the company's careers page).
"""
from __future__ import annotations

import json
import re

import requests

from .. import config

TENANTS_PATH = config.DATA_DIR / "workday_tenants.json"
HEAD = {"User-Agent": "Mozilla/5.0 (job-hunt-automation)", "Accept": "application/json"}
_CITY = ("bengaluru", "bangalore", "hyderabad", "secunderabad")
_TOO_SENIOR = re.compile(
    r"\b(staff|principal|director|vice\s*president|\bvp\b|head\s+of|distinguished|"
    r"fellow|chief|architect|senior\s+manager)\b", re.I)
_DAYS_RE = re.compile(r"(\d+)\+?\s*day", re.I)


def _days_old(posted: str) -> int | None:
    if not posted:
        return None
    if "today" in posted.lower():
        return 0
    m = _DAYS_RE.search(posted)
    return int(m.group(1)) if m else None


def _title_matches(title: str, keywords: list[str]) -> bool:
    low = title.lower()
    return any(kw.lower() in low for kw in keywords)


def _load_tenants() -> dict:
    if TENANTS_PATH.exists():
        try:
            return json.loads(TENANTS_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def _fetch_tenant(name: str, cfg: dict, keywords: list[str]) -> list[dict]:
    t, dc, site = cfg["tenant"], cfg["dc"], cfg["site"]
    base = f"https://{t}.{dc}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{t}/{site}/jobs"
    out: dict[str, dict] = {}
    for kw in keywords:
        offset = 0
        while offset < 60:  # cap pages per keyword
            try:
                r = requests.post(api, json={"appliedFacets": {}, "limit": 20,
                                             "offset": offset, "searchText": kw},
                                  headers=HEAD, timeout=12)
                if r.status_code != 200:
                    break
                posts = r.json().get("jobPostings", [])
            except Exception:  # noqa: BLE001
                break
            if not posts:
                break
            for p in posts:
                loc = (p.get("locationsText") or "").lower()
                title = p.get("title", "")
                if not any(c in loc for c in _CITY) or _TOO_SENIOR.search(title):
                    continue
                if not _title_matches(title, keywords):
                    continue
                path = p.get("externalPath", "")
                url = f"{base}/{site}{path}"
                out[url] = {"source": "workday", "title": title, "company": name,
                            "location": p.get("locationsText", ""), "url": url,
                            "description": title,
                            "posted": p.get("postedOn", "")}
            offset += 20
    return list(out.values())


def scrape(keywords: list[str]) -> list[dict]:
    tenants = _load_tenants()
    jobs: list[dict] = []
    for name, cfg in tenants.items():
        try:
            jobs.extend(_fetch_tenant(name, cfg, keywords[:4]))  # limit kw for speed
        except Exception as exc:  # noqa: BLE001
            print(f"  workday {name} failed: {exc}")
    return jobs
