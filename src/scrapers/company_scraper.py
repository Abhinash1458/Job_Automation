"""Free, Apify-free job sources that target YOUR company list:

  1. Greenhouse + Lever public boards (no API key) — probe each Excel company's
     careers board directly and keep Bangalore/Hyderabad roles matching keywords.
  2. Adzuna aggregator API (free key) — India-wide job search, then filtered to
     the company allowlist.

Both return the normalized shape documented in free_scraper.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import re

import requests

from .. import config, gcc_directory

HEAD = {"User-Agent": "Mozilla/5.0 (job-hunt-automation)"}
TIMEOUT = 8
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


def _probe_company(name: str, keywords: list[str]) -> list[dict]:
    out: list[dict] = []
    for slug in _slugs(name):
        # Greenhouse
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                             headers=HEAD, timeout=TIMEOUT)
            if r.status_code == 200:
                for j in r.json().get("jobs", []):
                    loc = (j.get("location") or {}).get("name", "")
                    if _in_target_city(loc) and _matches_kw(j.get("title", ""), keywords):
                        out.append({
                            "source": "greenhouse", "title": j.get("title", ""),
                            "company": name, "location": loc,
                            "url": j.get("absolute_url", ""),
                            "description": j.get("title", ""), "posted": j.get("updated_at", ""),
                        })
                if out:
                    return out
        except Exception:  # noqa: BLE001
            pass
        # Lever
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json",
                             headers=HEAD, timeout=TIMEOUT)
            if r.status_code == 200 and isinstance(r.json(), list):
                for j in r.json():
                    loc = (j.get("categories") or {}).get("location", "")
                    if _in_target_city(loc) and _matches_kw(j.get("text", ""), keywords):
                        out.append({
                            "source": "lever", "title": j.get("text", ""),
                            "company": name, "location": loc,
                            "url": j.get("hostedUrl", ""),
                            "description": (j.get("descriptionPlain") or "")[:2000],
                            "posted": "",
                        })
                if out:
                    return out
        except Exception:  # noqa: BLE001
            pass
    return out


def greenhouse_lever(keywords: list[str], max_workers: int = 20) -> list[dict]:
    companies = [n for n, _ in gcc_directory.load_excel()] or list(gcc_directory._SEED)
    jobs: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_probe_company, c, keywords) for c in companies]
        for f in cf.as_completed(futures):
            jobs.extend(f.result())
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
