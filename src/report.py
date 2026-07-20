"""Generate the daily review report — a self-contained HTML file listing the
top matched GCC jobs with scores, why-it-fits, and the apply link. You open it,
skim, and approve the ones you want (see the review commands in the header).
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

REPORTS_DIR = config.DATA_DIR / "reports"
# Committed folder: one dated+timestamped markdown file per run.
MATCHES_DIR = config.ROOT / "matches"


def days_old(posted: str) -> int | None:
    """Age of a posting in days from an ISO-ish date string, or None if unknown."""
    if not posted:
        return None
    s = posted.strip().replace("Z", "+00:00")
    for candidate in (s, s[:10]):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - dt).days)
        except ValueError:
            continue
    return None


def _reasons(materials_json: str | None) -> tuple[list[str], list[str]]:
    if not materials_json:
        return [], []
    try:
        data = json.loads(materials_json)
    except (TypeError, ValueError):
        return [], []
    return data.get("reasons", []), data.get("missing", [])


def _row(i: int, job: dict) -> str:
    reasons, missing = _reasons(job.get("materials"))
    score = job.get("score") or 0
    tier = "strong" if score >= 85 else "good" if score >= 70 else "weak"
    company = html.escape(job.get("company") or "")
    title = html.escape(job.get("title") or "")
    loc = html.escape(job.get("location") or "")
    url = html.escape(job.get("url") or "")
    tailored = "✅ packet ready" if job.get("materials") and '"cover_letter"' in (job.get("materials") or "") else "—"
    reason_html = "".join(f"<li>{html.escape(r)}</li>" for r in reasons[:4])
    miss_html = "".join(f"<li>{html.escape(m)}</li>" for m in missing[:3])
    return f"""
    <tr class="{tier}">
      <td class="num">{i}</td>
      <td class="score">{score}</td>
      <td>
        <div class="title">{title}</div>
        <div class="company">{company} · {loc}</div>
        <ul class="reasons">{reason_html}</ul>
        {f'<div class="miss"><b>Gaps:</b><ul>{miss_html}</ul></div>' if miss_html else ''}
      </td>
      <td class="tailor">{tailored}</td>
      <td><a href="{url}" target="_blank">Open&nbsp;posting →</a></td>
    </tr>"""


def build(date: str, jobs: list[dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = "".join(_row(i + 1, j) for i, j in enumerate(jobs))
    strong = sum(1 for j in jobs if (j.get("score") or 0) >= 85)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Hunt — {date}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; background: #0b0f17; color: #e6edf3; }}
  header {{ padding: 24px 28px; background: linear-gradient(135deg,#1f2937,#111827); border-bottom: 1px solid #30363d; }}
  h1 {{ margin: 0 0 6px; font-size: 22px; }}
  .sub {{ color: #9aa4b2; font-size: 14px; }}
  .how {{ margin-top: 14px; padding: 12px 14px; background: #0d1b2a; border: 1px solid #234; border-radius: 8px; font-size: 13px; }}
  code {{ background: #1f2a3a; padding: 2px 6px; border-radius: 4px; color: #7ee787; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td, th {{ padding: 12px 14px; border-bottom: 1px solid #21262d; vertical-align: top; text-align: left; }}
  th {{ position: sticky; top: 0; background: #161b22; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #8b949e; }}
  .num {{ color: #6e7681; }}
  .score {{ font-weight: 700; font-size: 18px; }}
  tr.strong .score {{ color: #3fb950; }}
  tr.good .score {{ color: #d29922; }}
  tr.weak .score {{ color: #8b949e; }}
  .title {{ font-weight: 600; }}
  .company {{ color: #9aa4b2; font-size: 13px; margin: 2px 0 6px; }}
  ul.reasons {{ margin: 4px 0; padding-left: 18px; color: #c9d1d9; font-size: 13px; }}
  .miss {{ font-size: 12px; color: #d29922; margin-top: 4px; }}
  .miss ul {{ margin: 2px 0; padding-left: 18px; }}
  a {{ color: #58a6ff; text-decoration: none; white-space: nowrap; }}
  a:hover {{ text-decoration: underline; }}
</style></head>
<body>
<header>
  <h1>Daily Job Matches — {date}</h1>
  <div class="sub">{len(jobs)} GCC / product roles in Bangalore &amp; Hyderabad · {strong} strong (85+) · ranked by fit to your resume</div>
  <div class="how">
    <b>Review:</b> skim the list, open the ones you like.
    <b>Approve</b> for assisted apply: <code>python -m src.main approve &lt;row#&gt;</code> (e.g. <code>approve 1 3 4</code>).
    Then run <code>python -m src.main apply</code> — it opens each approved job pre-filled for you to submit.
  </div>
</header>
<table>
  <thead><tr><th>#</th><th>Score</th><th>Role &amp; why it fits</th><th>Tailored</th><th>Apply</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""

    path = REPORTS_DIR / f"daily_{date}.html"
    path.write_text(doc, encoding="utf-8")
    return path


def _md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _age_label(d: int | None) -> str:
    if d is None:
        return "—"
    if d <= 7:
        return f"{d}d 🔥"
    if d <= 30:
        return f"{d}d"
    return f"{d}d ⏳"      # stale (>30d), sorted to the bottom


def build_markdown(date: str, rows: list[dict], new_urls: set | None = None) -> Path:
    """Markdown report from enriched rows. Writes a dated+timestamped file into
    matches/ AND updates LATEST_MATCHES.md (one-click view on GitHub).

    Each row: {score, title, company, location, url, reasons[list], posted, days_old, new}
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    strong = sum(1 for r in rows if (r.get("score") or 0) >= 85)
    new_count = sum(1 for r in rows if r.get("new"))
    recent = sum(1 for r in rows if (r.get("days_old") is not None and r["days_old"] <= 30))

    lines = [
        f"# Job Matches — {stamp} UTC",
        "",
        f"**{len(rows)} matches** at GCC / product companies in **Bangalore & Hyderabad** "
        f"· 🆕 {new_count} new · 🔥 {recent} posted within 30 days · {strong} strong (85+) "
        f"· matched to your ~3-yr AI/GenAI profile.",
        "",
        "Sorted: recent + best-fit first; roles older than 30 days (⏳) sink to the bottom.",
        "",
        "| # | Score | New | Age | Role | Company · Location | Why it fits | Apply |",
        "|---|------|-----|-----|------|--------------------|-------------|-------|",
    ]
    for i, r in enumerate(rows, 1):
        reasons = r.get("reasons") or []
        why = _md_escape("; ".join(reasons[:2]))
        score = r.get("score") or 0
        badge = "🟢" if score >= 85 else "🟡" if score >= 75 else "⚪"
        new = "🆕" if r.get("new") else ""
        lines.append(
            f"| {i} | {badge} {score} | {new} | {_age_label(r.get('days_old'))} | "
            f"{_md_escape(r.get('title'))} | "
            f"{_md_escape(r.get('company'))} · {_md_escape(r.get('location'))} | "
            f"{why} | [Apply]({r.get('url')}) |"
        )
    lines += ["", "---",
              f"*Auto-updated daily at 6 AM IST. Snapshot: {stamp} UTC. "
              "Older snapshots are in the [matches/](matches/) folder.*", ""]
    md = "\n".join(lines)

    dated = MATCHES_DIR / f"matches_{stamp}.md"
    dated.write_text(md, encoding="utf-8")
    (config.ROOT / "LATEST_MATCHES.md").write_text(md, encoding="utf-8")
    return dated
