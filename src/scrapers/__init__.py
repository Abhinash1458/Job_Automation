"""Job scrapers. `scrape_jobs` picks Apify if a token is set, else a free source."""
from __future__ import annotations

from .. import config
from . import apify_scraper, free_scraper


def scrape_jobs(keywords: list[str], location: str, limit: int) -> list[dict]:
    """Return a list of normalized job dicts (see NORMALIZED SHAPE in free_scraper)."""
    if config.APIFY_TOKEN:
        try:
            jobs = apify_scraper.scrape(keywords, location, limit)
            if jobs:
                return jobs
            print("Apify returned no jobs; falling back to free scraper.")
        except Exception as exc:  # noqa: BLE001 - surface + fall back, don't crash the run
            print(f"Apify scrape failed ({exc}); falling back to free scraper.")
    return free_scraper.scrape(keywords, location, limit)
