"""The daily 6 AM pipeline.

  1. Refresh the GCC directory (Bangalore + Hyderabad), once per day.
  2. Scrape AI/GenAI jobs for each target city (Apify).
  3. Keep ONLY jobs at GCC / product companies (drop IT-services firms).
  4. Score each against the resume (Claude), skip already-seen jobs.
  5. Rank, take the top N (default 50), tailor materials for the strongest.
  6. Mark them 'for_review' and write a daily HTML report to open and approve.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import config, gcc_directory, matcher, report, resume_parser, tailor, tracker
from .scrapers import scrape_jobs


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def run(tailor_top: int = 20, fresh: bool = False) -> str:
    """Run the daily pipeline.

    Surfaces ALL jobs that closely match the resume (score >= MATCH_THRESHOLD),
    not a fixed top-50. `fresh=True` (used in CI) skips the already-seen filter so
    every run is a full snapshot of current matches even without a persistent DB.
    """
    config.require_llm()
    profile = resume_parser.load_profile()

    print("[1/6] Refreshing GCC directory ...")
    total = gcc_directory.refresh()
    print(f"      {total} GCCs in allowlist")

    print(f"[2/6] Scraping jobs for {config.JOB_KEYWORDS} in {config.JOB_LOCATIONS} ...")
    from .scrapers import company_scraper
    raw: list[dict] = []
    seen_urls: set[str] = set()

    def _add(jobs: list[dict], label: str) -> None:
        n = 0
        for j in jobs:
            if j.get("url") and j["url"] not in seen_urls:
                seen_urls.add(j["url"])
                raw.append(j)
                n += 1
        print(f"      {label}: {n}")

    # 1) Company boards (Greenhouse/Lever, no key) — targets your Excel companies
    _add(company_scraper.greenhouse_lever(config.JOB_KEYWORDS), "greenhouse/lever")
    # 2) Adzuna aggregator (free key) — India jobs, filtered to the allowlist
    _add(company_scraper.adzuna(config.JOB_KEYWORDS, config.JOB_LOCATIONS), "adzuna")
    # 3) Apify (only if a token + paid actor is configured)
    if config.APIFY_TOKEN:
        for loc in config.JOB_LOCATIONS:
            _add(scrape_jobs(config.JOB_KEYWORDS, loc, config.MAX_JOBS_PER_RUN), f"apify {loc}")
    print(f"      {len(raw)} raw jobs total")

    print("[3/6] Filtering to GCC / product companies ...")
    gcc_jobs = [j for j in raw if gcc_directory.is_gcc(j.get("company", ""))]
    print(f"      {len(gcc_jobs)} GCC jobs (dropped {len(raw) - len(gcc_jobs)} non-GCC)")

    print("[4/6] Scoring jobs against your resume ...")
    scored: list[tuple[int, dict]] = []
    new_count = 0
    for job in gcc_jobs:
        if not fresh and tracker.seen(job["url"]):
            continue
        tracker.record_seen(job)
        new_count += 1
        try:
            result = matcher.score_job(profile, job)
        except Exception as exc:  # noqa: BLE001
            print(f"      scoring failed for {job.get('company')}: {exc}")
            continue
        job["_score"] = result["score"]
        job["_verdict"] = result["verdict"]
        job["_reasons"] = result.get("reasons", [])
        job["_missing"] = result.get("missing", [])
        tracker.update(job["url"], score=result["score"], verdict=result["verdict"])
        scored.append((result["score"], job))
    print(f"      scored {new_count} new jobs")

    print(f"[5/6] Selecting close matches (score >= {config.MATCH_THRESHOLD}) "
          f"and tailoring top {tailor_top} ...")
    scored.sort(key=lambda t: t[0], reverse=True)
    close = [j for s, j in scored if s >= config.MATCH_THRESHOLD]
    today = _today()
    for i, job in enumerate(close):
        materials = None
        if i < tailor_top:
            try:
                materials = tailor.tailor(profile, job)
            except Exception as exc:  # noqa: BLE001
                print(f"      tailoring failed for {job.get('company')}: {exc}")
        tracker.update(
            job["url"], status="for_review", surfaced_date=today,
            materials=materials if materials else {"reasons": job["_reasons"],
                                                   "missing": job["_missing"]},
        )
    print(f"      {len(close)} close matches surfaced")

    print("[6/6] Writing daily reports (HTML + Markdown) ...")
    jobs = tracker.top_for_review(today, 10000)
    html_path = report.build(today, jobs)
    md_path = report.build_markdown(today, jobs)
    print(f"      HTML: {html_path}")
    print(f"      Markdown: {md_path}")
    return str(md_path)
