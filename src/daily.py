"""The daily 6 AM pipeline.

  1. Refresh the GCC directory (Bangalore + Hyderabad), once per day.
  2. Scrape AI/GenAI jobs for each target city (Apify).
  3. Keep ONLY jobs at GCC / product companies (drop IT-services firms).
  4. Score each against the resume (Claude), skip already-seen jobs.
  5. Rank, take the top N (default 50), tailor materials for the strongest.
  6. Mark them 'for_review' and write a daily HTML report to open and approve.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config, gcc_directory, matcher, report, resume_parser, tailor, tracker
from .scrapers import scrape_jobs

SEEN_PATH = config.DATA_DIR / "seen_jobs.json"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_seen() -> dict:
    if SEEN_PATH.exists():
        try:
            return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def run(tailor_top: int | None = None, fresh: bool = False) -> str:
    """Run the daily pipeline.

    Surfaces ALL jobs that closely match the resume (score >= MATCH_THRESHOLD),
    not a fixed top-50. `fresh=True` (used in CI) skips the already-seen filter so
    every run is a full snapshot of current matches even without a persistent DB.
    """
    config.require_llm()
    if tailor_top is None:
        tailor_top = config.TAILOR_TOP
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

    # 1) Company boards (Greenhouse/Lever/Ashby/SmartRecruiters/Recruitee, no key)
    _add(company_scraper.company_boards(config.JOB_KEYWORDS), "company boards")
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
        # always keep the fit reasons; add the tailored packet for the top ones
        materials = {"reasons": job["_reasons"], "missing": job["_missing"]}
        if i < tailor_top:
            try:
                materials.update(tailor.tailor(profile, job))
            except Exception as exc:  # noqa: BLE001
                print(f"      tailoring failed for {job.get('company')}: {exc}")
        tracker.update(job["url"], status="for_review", surfaced_date=today,
                       materials=materials)
    print(f"      {len(close)} close matches surfaced")

    # Track which jobs are new vs. previously seen (for the 🆕 marker).
    seen = _load_seen()
    new_urls = set()
    for job in close:
        if job["url"] not in seen:
            new_urls.add(job["url"])
            seen[job["url"]] = today
    SEEN_PATH.write_text(json.dumps(seen, indent=2), encoding="utf-8")

    # Build enriched rows, sorted: recent + best-fit first, stale (>30d) last.
    rows = []
    for job in close:
        d = report.days_old(job.get("posted", ""))
        rows.append({
            "score": job["_score"], "title": job.get("title", ""),
            "company": job.get("company", ""), "location": job.get("location", ""),
            "url": job["url"], "reasons": job.get("_reasons", []),
            "posted": job.get("posted", ""), "days_old": d,
            "new": job["url"] in new_urls,
        })
    rows.sort(key=lambda r: (
        (r["days_old"] is not None and r["days_old"] > 30),  # stale sinks
        -(r["score"] or 0),                                  # then best fit
    ))

    print(f"[6/6] Writing daily reports ({len(new_urls)} new today) ...")
    md_path = report.build_markdown(today, rows, new_urls)
    print(f"      Markdown: {md_path}")
    return str(md_path)
