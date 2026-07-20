"""Apify-based job scraping.

Runs an Apify actor (default: a LinkedIn jobs scraper) and normalizes its
output into the shape documented in free_scraper.py.

Different actors return different field names, so `_normalize` is best-effort
and tolerant. If you swap APIFY_JOBS_ACTOR for a different actor, adjust the
`run_input` and field mapping below to match that actor's schema.
"""
from __future__ import annotations

from .. import config


def _first(d: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


def _normalize(item: dict) -> dict:
    return {
        "source": "apify",
        "title": _first(item, "title", "jobTitle", "position"),
        "company": _first(item, "companyName", "company", "employer"),
        "location": _first(item, "location", "jobLocation", "place"),
        "url": _first(item, "url", "jobUrl", "link", "applyUrl"),
        "description": _first(item, "description", "descriptionText", "jobDescription"),
        "posted": _first(item, "postedAt", "publishedAt", "date"),
    }


def scrape(keywords: list[str], location: str, limit: int) -> list[dict]:
    from apify_client import ApifyClient

    client = ApifyClient(config.APIFY_TOKEN)

    # Common input shape for LinkedIn/Indeed-style actors. Adjust per actor.
    run_input = {
        "title": ", ".join(keywords),
        "location": location,
        "rows": limit,
        "maxItems": limit,
    }

    run = client.actor(config.APIFY_JOBS_ACTOR).call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []

    jobs = [_normalize(item) for item in client.dataset(dataset_id).iterate_items()]
    return [j for j in jobs if j["url"]][:limit]
