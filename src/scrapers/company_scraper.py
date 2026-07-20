"""Free, Apify-free job sources that target YOUR company list.

Probes each company's public careers board across several ATS platforms
(Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee), keeps ONLY
Bangalore/Hyderabad roles that match the target keywords, and drops roles that
are clearly too senior for a ~mid-level (3-year) candidate.

A verified company->board map is cached in data/ats_boards.json (built by
build_ats_map) so daily runs query only known-good boards — fast and stable.

All functions return the normalized shape documented in free_scraper.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import json
import re

import requests

from .. import config, gcc_directory

HEAD = {"User-Agent": "Mozilla/5.0 (job-hunt-automation)"}
TIMEOUT = 12
RETRIES = 2
ATS_MAP = config.DATA_DIR / "ats_boards.json"

# Strict: only these cities count (no "India"/remote/other cities).
_CITY_HINTS = ("bengaluru", "bangalore", "bangaluru", "hyderabad", "hyderbad", "secunderabad")

# Titles at/above these levels need far more than ~3 years — drop them.
_TOO_SENIOR = re.compile(
    r"\b(staff|principal|director|vice\s*president|\bvp\b|head\s+of|distinguished|"
    r"fellow|chief|architect|senior\s+manager|sr\.?\s+manager|engineering\s+manager|"
    r"group\s+manager|lead\s+manager)\b", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


def _matches_kw(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def _in_target_city(loc: str) -> bool:
    low = (loc or "").lower()
    return any(h in low for h in _CITY_HINTS)


def _too_senior(title: str) -> bool:
    return bool(_TOO_SENIOR.search(title or ""))


def _keep(title: str, loc: str, keywords: list[str]) -> bool:
    return bool(title) and _in_target_city(loc) and _matches_kw(title, keywords) \
        and not _too_senior(title)


def _get(url: str):
    for _ in range(RETRIES + 1):
        try:
            r = requests.get(url, headers=HEAD, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 400):
                return None
        except Exception:  # noqa: BLE001
            continue
    return None


# ------------------------- per-platform fetchers ----------------------------
# Each returns a list of normalized jobs (already city/keyword/seniority filtered).

def _gh(slug: str, name: str, kw: list[str]) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    out = []
    for j in (data or {}).get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        if _keep(j.get("title", ""), loc, kw):
            out.append({"source": "greenhouse", "title": j.get("title", ""), "company": name,
                        "location": loc, "url": j.get("absolute_url", ""),
                        "description": _strip(j.get("content", ""))[:2500],
                        "posted": j.get("updated_at", "")})
    return out


def _lever(slug: str, name: str, kw: list[str]) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in data or []:
        loc = (j.get("categories") or {}).get("location", "")
        if _keep(j.get("text", ""), loc, kw):
            out.append({"source": "lever", "title": j.get("text", ""), "company": name,
                        "location": loc, "url": j.get("hostedUrl", ""),
                        "description": (j.get("descriptionPlain") or "")[:2500], "posted": ""})
    return out


def _ashby(slug: str, name: str, kw: list[str]) -> list[dict]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    out = []
    for j in (data or {}).get("jobs", []):
        loc = j.get("location", "") or j.get("locationName", "")
        if _keep(j.get("title", ""), loc, kw):
            out.append({"source": "ashby", "title": j.get("title", ""), "company": name,
                        "location": loc, "url": j.get("jobUrl", ""),
                        "description": _strip(j.get("descriptionHtml", ""))[:2500], "posted": ""})
    return out


def _smartrecruiters(slug: str, name: str, kw: list[str]) -> list[dict]:
    data = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100")
    out = []
    for j in (data or {}).get("content", []):
        loc_obj = j.get("location") or {}
        loc = f"{loc_obj.get('city','')} {loc_obj.get('country','')}".strip()
        if _keep(j.get("name", ""), loc, kw):
            out.append({"source": "smartrecruiters", "title": j.get("name", ""), "company": name,
                        "location": loc,
                        "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id','')}",
                        "description": j.get("name", ""), "posted": j.get("releasedDate", "")})
    return out


def _recruitee(slug: str, name: str, kw: list[str]) -> list[dict]:
    data = _get(f"https://{slug}.recruitee.com/api/offers/")
    out = []
    for j in (data or {}).get("offers", []):
        loc = f"{j.get('city','')} {j.get('country','')}".strip()
        if _keep(j.get("title", ""), loc, kw):
            out.append({"source": "recruitee", "title": j.get("title", ""), "company": name,
                        "location": loc, "url": j.get("careers_url", ""),
                        "description": _strip(j.get("description", ""))[:2500], "posted": ""})
    return out


PLATFORMS = {
    "greenhouse": _gh, "lever": _lever, "ashby": _ashby,
    "smartrecruiters": _smartrecruiters, "recruitee": _recruitee,
}

# Detector URLs to check whether a company has a board on a platform.
_DETECT = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{s}/jobs",
    "lever": "https://api.lever.co/v0/postings/{s}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{s}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=1",
    "recruitee": "https://{s}.recruitee.com/api/offers/",
}


def _has_jobs(platform: str, data) -> bool:
    if not data:
        return False
    if platform in ("greenhouse", "ashby"):
        return bool(data.get("jobs"))
    if platform == "lever":
        return isinstance(data, list) and bool(data)
    if platform == "smartrecruiters":
        return bool(data.get("content"))
    if platform == "recruitee":
        return bool(data.get("offers"))
    return False


# ------------------------- slugs + board discovery --------------------------

_STOP_SLUGS = {"general", "global", "national", "international", "systems",
               "technology", "technologies", "solutions", "services", "group"}


def _slugs(name: str) -> list[str]:
    base = name.split("(")[0]
    words = [w for w in re.findall(r"[a-z0-9]+", base.lower())
             if w not in gcc_directory._GENERIC]
    cands: list[str] = []
    compact = "".join(words)
    if len(compact) >= 4:
        cands.append(compact)
    if words and len(words[0]) >= 5 and words[0] not in _STOP_SLUGS:
        cands.append(words[0])
    if len(words) >= 2:
        cands.append("-".join(words[:2]))     # e.g. "wells-fargo" (lever/ashby style)
    return list(dict.fromkeys(cands))


def _get_fast(url: str):
    """Single-shot GET with a short timeout — for bulk board detection."""
    try:
        r = requests.get(url, headers=HEAD, timeout=6)
        return r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _find_board(name: str):
    """Return (platform, slug) for the first board that exists with jobs."""
    for slug in _slugs(name):
        for platform, tmpl in _DETECT.items():
            if _has_jobs(platform, _get_fast(tmpl.format(s=slug))):
                return (platform, slug)
    return None


def build_ats_map(max_workers: int = 12) -> dict:
    """One-time: probe every company across all ATS platforms; cache the hits."""
    companies = [n for n, _ in gcc_directory.load_excel()] or list(gcc_directory._SEED)
    found: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for name, board in ex.map(lambda c: (c, _find_board(c)), companies):
            if board:
                found[name] = {"platform": board[0], "slug": board[1]}
    ATS_MAP.write_text(json.dumps(found, indent=2), encoding="utf-8")
    return found


# ------------------------------ public API ----------------------------------

def company_boards(keywords: list[str], max_workers: int = 24) -> list[dict]:
    """Fetch matching jobs from every cached company board (fast, stable)."""
    if not ATS_MAP.exists():
        return _live_probe(keywords, max_workers)
    boards = json.loads(ATS_MAP.read_text(encoding="utf-8"))

    def _fetch(item):
        name, b = item
        fn = PLATFORMS.get(b["platform"])
        return fn(b["slug"], name, keywords) if fn else []

    jobs: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for res in ex.map(_fetch, boards.items()):
            jobs.extend(res)
    return jobs


def _live_probe(keywords: list[str], max_workers: int) -> list[dict]:
    companies = [n for n, _ in gcc_directory.load_excel()] or list(gcc_directory._SEED)

    def _probe(name):
        board = _find_board(name)
        if not board:
            return []
        return PLATFORMS[board[0]](board[1], name, keywords)

    jobs: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for res in ex.map(_probe, companies):
            jobs.extend(res)
    return jobs


# back-compat alias
greenhouse_lever = company_boards


# ------------------------------- Adzuna -------------------------------------

def adzuna(keywords: list[str], locations: list[str], per_page: int = 50) -> list[dict]:
    if not (config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY):
        return []
    jobs: list[dict] = []
    for city in locations:
        for kw in keywords:
            try:
                r = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/in/search/1",
                    params={"app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
                            "results_per_page": per_page, "what": kw, "where": city,
                            "content-type": "application/json"},
                    headers=HEAD, timeout=15)
                if r.status_code != 200:
                    continue
                for j in r.json().get("results", []):
                    company = (j.get("company") or {}).get("display_name", "")
                    loc = (j.get("location") or {}).get("display_name", city)
                    if not gcc_directory.is_gcc(company):
                        continue
                    if _too_senior(j.get("title", "")) or not _in_target_city(loc):
                        continue
                    jobs.append({"source": "adzuna", "title": j.get("title", ""),
                                 "company": company, "location": loc,
                                 "url": j.get("redirect_url", ""),
                                 "description": j.get("description", ""),
                                 "posted": j.get("created", "")})
            except Exception:  # noqa: BLE001
                continue
    return jobs
