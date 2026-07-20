"""Job Hunt Automation — pipeline entry point.

Usage:
    python -m src.main parse            # parse your resume -> data/profile.json
    python -m src.main run              # one-off scrape -> match -> tailor -> draft outreach
    python -m src.main daily            # the 6 AM job: GCC jobs -> score -> top 50 -> review report
    python -m src.main review           # open today's review report in your browser
    python -m src.main approve 1 3 4    # approve report row numbers for assisted apply
    python -m src.main apply            # open each approved job pre-filled; you submit
    python -m src.main status           # show tracker stats + recent activity
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from . import config, contact_finder, daily, emailer, matcher, report, resume_parser, tailor, tracker
from .scrapers import scrape_jobs

console = Console()


def cmd_parse(_args) -> None:
    config.require_anthropic()
    resume = resume_parser.find_resume()
    if resume is None:
        console.print(f"[red]No resume found.[/] Drop a PDF/DOCX/TXT into {config.RESUME_DIR}")
        sys.exit(1)
    console.print(f"Parsing [cyan]{resume.name}[/] ...")
    profile = resume_parser.parse(resume)
    console.print(f"[green]OK[/] -> {config.PROFILE_PATH}")
    console.print(f"  Name: {profile.get('full_name')}")
    console.print(f"  Skills: {', '.join(profile.get('skills', [])[:12])}")


def cmd_run(_args) -> None:
    config.require_anthropic()
    profile = resume_parser.load_profile()

    console.print(f"[bold]Scraping[/] up to {config.MAX_JOBS_PER_RUN} jobs/location "
                  f"for {config.JOB_KEYWORDS} in {config.JOB_LOCATIONS} ...")
    jobs: list[dict] = []
    seen_urls: set[str] = set()
    for loc in config.JOB_LOCATIONS:
        found = scrape_jobs(config.JOB_KEYWORDS, loc, config.MAX_JOBS_PER_RUN)
        for j in found:
            if j.get("url") and j["url"] not in seen_urls:
                seen_urls.add(j["url"])
                j["search_location"] = loc
                jobs.append(j)
        console.print(f"  [{loc}] found {len(found)}")
    console.print(f"  total unique: [cyan]{len(jobs)}[/] jobs\n")

    processed = drafted = 0
    for job in jobs:
        url = job.get("url")
        if not url or tracker.seen(url):
            continue
        tracker.record_seen(job)
        processed += 1

        label = f"{job.get('title','?')} @ {job.get('company','?')}"
        result = matcher.score_job(profile, job)
        score, verdict = result["score"], result["verdict"]
        tracker.update(url, score=score, verdict=verdict)

        color = "green" if score >= config.MATCH_THRESHOLD else "yellow"
        console.print(f"[{color}]{score:3d}[/] {label}  ({verdict})")

        if score < config.MATCH_THRESHOLD:
            tracker.update(url, status="skipped")
            continue

        # Tailor application materials (cover letter + answers).
        materials = tailor.tailor(profile, job)
        tracker.update(url, status="tailored", materials=materials)
        console.print(f"      [dim]tailored cover letter + {len(materials['answers'])} answers[/]")

        # Look for a hiring contact and draft outreach.
        contact = contact_finder.find(job)
        tracker.update(url, contact=contact)
        if contact.get("has_contact"):
            mail = emailer.compose(profile, job, contact, materials["pitch"])
            path = emailer.save_draft(job, contact, mail["subject"], mail["body"])
            tracker.update(url, status="outreach_drafted", draft_path=str(path))
            drafted += 1
            to = contact.get("email") or contact.get("name") or "hiring team"
            console.print(f"      [green]drafted outreach[/] to {to} -> {path.name}")

    console.print(f"\n[bold]Done.[/] processed {processed} new jobs, "
                  f"drafted {drafted} outreach emails.")
    console.print(f"Review drafts in [cyan]{config.DRAFTS_DIR}[/], "
                  f"then `python -m src.main status`.")


def cmd_daily(args) -> None:
    path = daily.run(fresh=getattr(args, "fresh", False))
    console.print(f"\n[green]Daily run complete.[/] Report:")
    console.print(f"  [cyan]{path}[/]")
    console.print("  or run [bold]python -m src.main review[/]")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def cmd_review(_args) -> None:
    """Launch the interactive checklist web app (tick ✓ to apply, ✗ to skip)."""
    if not tracker.top_for_review(_today(), 1):
        console.print("[yellow]No jobs awaiting review today.[/] Run `python -m src.main daily` first.")
        return
    from . import review_app
    review_app.serve()


def cmd_report(_args) -> None:
    """Open the static HTML report (read-only) instead of the interactive app."""
    path = report.REPORTS_DIR / f"daily_{_today()}.html"
    if not path.exists():
        reports = sorted(report.REPORTS_DIR.glob("daily_*.html"))
        if not reports:
            console.print("[yellow]No report yet.[/] Run `python -m src.main daily` first.")
            return
        path = reports[-1]
    console.print(f"Opening [cyan]{path}[/]")
    webbrowser.open(path.as_uri())


def cmd_approve(args) -> None:
    jobs = tracker.top_for_review(_today(), 50)
    if not jobs:
        console.print("[yellow]No jobs awaiting review today.[/] Run `daily` first.")
        return
    approved = 0
    for n in args.rows:
        if 1 <= n <= len(jobs):
            tracker.approve(jobs[n - 1]["url"])
            console.print(f"[green]approved[/] #{n}: {jobs[n-1]['company']} — {jobs[n-1]['title']}")
            approved += 1
        else:
            console.print(f"[red]skip[/] #{n}: out of range (1-{len(jobs)})")
    console.print(f"\n{approved} approved. Run [bold]python -m src.main apply[/] to apply.")


def cmd_apply(_args) -> None:
    from . import applier
    applier.run()


def cmd_status(_args) -> None:
    stats = tracker.stats()
    console.print("[bold]Pipeline status[/]")
    for k, v in sorted(stats.items()):
        console.print(f"  {k:18s} {v}")

    table = Table(title="\nRecent activity", show_lines=False)
    for col in ("Score", "Verdict", "Status", "Title", "Company", "Draft"):
        table.add_column(col)
    for r in tracker.recent(20):
        table.add_row(
            str(r.get("score") or ""), r.get("verdict") or "", r.get("status") or "",
            (r.get("title") or "")[:40], (r.get("company") or "")[:24],
            (r.get("draft_path") or "").split("\\")[-1].split("/")[-1],
        )
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(prog="job-hunt", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("parse", help="parse resume into profile.json")
    sub.add_parser("run", help="one-off scrape->match->tailor->draft pipeline")
    dp = sub.add_parser("daily", help="6 AM job: GCC jobs -> score -> all close matches -> report")
    dp.add_argument("--fresh", action="store_true",
                    help="score every match ignoring the seen-before filter (used in CI)")
    sub.add_parser("review", help="interactive checklist: tick to apply, cross to skip")
    sub.add_parser("report", help="open the static (read-only) HTML report instead")
    ap = sub.add_parser("approve", help="approve report row numbers (CLI alternative to ticking)")
    ap.add_argument("rows", nargs="+", type=int, help="row numbers from the report, e.g. 1 3 4")
    sub.add_parser("apply", help="open each approved job pre-filled; you submit")
    sub.add_parser("status", help="show tracker stats and recent activity")

    args = parser.parse_args()
    {
        "parse": cmd_parse, "run": cmd_run, "daily": cmd_daily, "review": cmd_review,
        "report": cmd_report, "approve": cmd_approve, "apply": cmd_apply, "status": cmd_status,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
