"""Free, Apify-free job sources that target YOUR company list:

  1. Greenhouse + Lever public boards (no API key) — probe each Excel company's
     careers board directly and keep Bangalore/Hyderabad roles matching keywords.
  2. Adzuna aggregator API (free key) — India-wide job search, then filtered to
     the company allowlist.

Both return the normalized shape documented in free_scraper.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re

import requests

from .. import config, gcc_directory

HEAD = {"User-Agent": "Mozilla/5.0 (job-hunt-automation)"}
TIMEOUT = 12
RETRIES = 2
# Cached map of company -> verified careers board, built once by build_ats_map().
# Committed to the repo so daily runs query only known-good boards (fast + stable).
ATS_MAP = config.DATA_DIR / "ats_boards.json"
_CITY_HINTS = ("bangalore", "bengaluru", "hyderabad", "india")
# slugs that are too generic to trust as a company board
_STOP_SLUGS = {"general", "global", "national", "international", "systems",
               "technology", "technologies", "solutions", "services", "group"}


def _matches_kw(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def _in_target_city(loc: str) -> bool:
    low = (loc or "").lower()
    return any(h in low for h in _CITY_HINTS)


# ------------------------- Greenhouse / Lever -------------------------------

def _slugs(name: str) -> list[str]:
    base = name.split("(")[0]
    words = re.findall(r"[a-z0-9]+", base.lower())
    words = [w for w in words if w not in gcc_directory._GENERIC]
    cands: list[str] = []
    compact = "".join(words)
    if len(compact) >= 4:
        cands.append(compact)              # e.g. "wellsfargo"
    if words and len(words[0]) >= 5 and words[0] not in _STOP_SLUGS:
        cands.append(words[0])             # e.g. "tenstorrent"
    return list(dict.fromkeys(cands))


def _get(url: str):
    """GET with a couple of retries; returns parsed JSON or None."""
    for _ in range(RETRIES + 1):
        try:
            r = requests.get(url, headers=HEAD, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception:  # noqa: BLE001
            continue
    return None


def _gh_jobs(slug: str, name: str, keywords: list[str]) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    out = []
    for j in (data or {}).get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        if _in_target_city(loc) and _matches_kw(j.get("title", ""), keywords):
            out.append({"source": "greenhouse", "title": j.get("title", ""), "company": name,
                        "location": loc, "url": j.get("absolute_url", ""),
                        "description": j.get("title", ""), "posted": j.get("updated_at", "")})
    return out


def _lever_jobs(slug: str, name: str, keywords: list[str]) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in data or []:
        loc = (j.get("categories") or {}).get("location", "")
        if _in_target_city(loc) and _matches_kw(j.get("text", ""), keywords):
            out.append({"source": "lever", "title": j.get("text", ""), "company": name,
                        "location": loc, "url": j.get("hostedUrl", ""),
                        "description": (j.get("descriptionPlain") or "")[:2000], "posted": ""})
    return out


def _find_board(name: str):
    """Return (platform, slug) if a company has a Greenhouse/Lever board with jobs."""
    for slug in _slugs(name):
        gh = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        if gh and gh.get("jobs"):
            return ("greenhouse", slug)
        lv = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if isinstance(lv, list) and lv:
            return ("lever", slug)
    return None


def build_ats_map(max_workers: int = 15) -> dict:
    """One-time: probe every company and cache which have a Greenhouse/Lever board.
    Writes data/ats_boards.json so daily runs are fast and deterministic."""
    companies = [n for n, _ in gcc_directory.load_excel()] or list(gcc_directory._SEED)
    found: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = ex.map(lambda c: (c, _find_board(c)), companies)
        for name, board in results:
            if board:
                found[name] = {"platform": board[0], "slug": board[1]}
    ATS_MAP.write_text(json.dumps(found, indent=2), encoding="utf-8")
    return found


def greenhouse_lever(keywords: list[str], max_workers: int = 20) -> list[dict]:
    jobs: list[dict] = []
    if ATS_MAP.exists():
        # Fast, stable path: query only the known-good boards.
        boards = json.loads(ATS_MAP.read_text(encoding="utf-8"))

        def _fetch(item):
            name, b = item
            fn = _gh_jobs if b["platform"] == "greenhouse" else _lever_jobs
            return fn(b["slug"], name, keywords)

        with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
            for res in ex.map(_fetch, boards.items()):
                jobs.extend(res)
        return jobs

    # Fallback (no cache yet): live-probe every company.
    companies = [n for n, _ in gcc_directory.load_excel()] or list(gcc_directory._SEED)

    def _probe(name):
        board = _find_board(name)
        if not board:
            return []
        fn = _gh_jobs if board[0] == "greenhouse" else _lever_jobs
        return fn(board[1], name, keywords)

    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for res in ex.map(_probe, companies):
            jobs.extend(res)
    return jobs


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
                    params={
                        "app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
                        "results_per_page": per_page, "what": kw, "where": city,
                        "content-type": "application/json",
                    }, headers=HEAD, timeout=15,
                )
                if r.status_code != 200:
                    continue
                for j in r.json().get("results", []):
                    company = (j.get("company") or {}).get("display_name", "")
                    if not gcc_directory.is_gcc(company):
                        continue
                    jobs.append({
                        "source": "adzuna", "title": j.get("title", ""),
                        "company": company,
                        "location": (j.get("location") or {}).get("display_name", city),
                        "url": j.get("redirect_url", ""),
                        "description": j.get("description", ""),
                        "posted": j.get("created", ""),
                    })
            except Exception:  # noqa: BLE001
                continue
    return jobs
