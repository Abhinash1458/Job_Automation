"""Generate the daily review report — a self-contained HTML file listing the
top matched GCC jobs with scores, why-it-fits, and the apply link. You open it,
skim, and approve the ones you want (see the review commands in the header).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import config

REPORTS_DIR = config.DATA_DIR / "reports"


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


def build_markdown(date: str, jobs: list[dict]) -> Path:
    """Markdown report — renders on GitHub (viewable on your phone). Also writes
    LATEST_MATCHES.md at the repo root so it's one click from the repo homepage."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    strong = sum(1 for j in jobs if (j.get("score") or 0) >= 85)

    lines = [
        f"# Job Matches — {date}",
        "",
        f"**{len(jobs)} close matches** at GCC / product companies in Bangalore & Hyderabad "
        f"· {strong} strong (85+) · ranked by fit to your resume. Apply to the ones you like.",
        "",
        "| # | Score | Role | Company · Location | Why it fits | Apply |",
        "|---|------|------|--------------------|-------------|-------|",
    ]
    for i, j in enumerate(jobs, 1):
        reasons, _ = _reasons(j.get("materials"))
        why = _md_escape("; ".join(reasons[:2])) if reasons else ""
        score = j.get("score") or 0
        badge = "🟢" if score >= 85 else "🟡" if score >= 75 else "⚪"
        lines.append(
            f"| {i} | {badge} {score} | {_md_escape(j.get('title'))} | "
            f"{_md_escape(j.get('company'))} · {_md_escape(j.get('location'))} | "
            f"{why} | [Apply]({j.get('url')}) |"
        )
    lines += ["", "---", "*Generated automatically by the daily job-hunt pipeline.*", ""]
    md = "\n".join(lines)

    path = REPORTS_DIR / f"daily_{date}.md"
    path.write_text(md, encoding="utf-8")
    # also update the repo-root pointer file
    (config.ROOT / "LATEST_MATCHES.md").write_text(md, encoding="utf-8")
    return path
