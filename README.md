# Job Hunt Automation

Resume-driven job-hunting pipeline. It scrapes jobs, scores each against your
resume with Claude, writes a tailored cover letter + application answers for the
good ones, looks for a hiring-team contact, and drafts a personalized outreach
email for you to review and send.

```
resume  ─►  profile.json  ─►  scrape jobs  ─►  score (Claude)  ─►  tailor (Claude)
                                                                       │
                                                    find hiring contact ─►  draft email
                                                                       │
                                                              SQLite tracker (no double-apply)
```

## What's automatic vs. manual

| Step                    | Automatic? |
|-------------------------|------------|
| Scrape jobs             | ✅ (Apify if configured, else free public APIs) |
| Score fit vs. resume    | ✅ Claude |
| Cover letter + answers  | ✅ Claude, saved per job |
| Find hiring contact     | ✅ best-effort from the posting |
| **Outreach email**      | ✍️ **drafted only** — you review + send (your chosen setting) |
| Submit the application  | Materials are generated & stored ready to paste/submit. True one-click auto-submit on LinkedIn/Indeed needs per-site browser automation + login and violates most sites' ToS, so it's intentionally left as a review step. |

## Setup

1. **Create your config**

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and set an **LLM API key**. The provider is auto-detected by
   the key prefix, so any of these work:
   - `GROQ_API_KEY=gsk_...` (Groq — fast open models like Llama-3.3-70B) ← current
   - `ANTHROPIC_API_KEY=sk-ant-...` (Claude)
   - `XAI_API_KEY=xai-...` (Grok) · `OPENAI_API_KEY=sk-...` (OpenAI)

   Override the model with `LLM_MODEL=` if you like. Fill in your contact details
   and `JOB_KEYWORDS` / `JOB_LOCATION`.

2. **Add your resume** — drop a PDF, DOCX, or TXT into `data/resume/`.

3. **Dependencies** are already installed in `.venv`. To activate it:

   - PowerShell: `.\.venv\Scripts\Activate.ps1`
   - Git Bash:   `source .venv/Scripts/activate`

   (Or just call `.venv/Scripts/python.exe` directly.)

## Usage

### Daily GCC pipeline (the main workflow)

Every morning at 6 AM (via Task Scheduler) the pipeline:
1. refreshes the GCC directory (Bangalore + Hyderabad) from businessofgcc.com,
2. scrapes AI/GenAI jobs (Apify),
3. keeps **only GCC / product companies** (IT-services firms are dropped),
4. scores each against your resume (Claude),
5. ranks the **top 50**, tailors materials for the strongest, and
6. writes a review report you open when free.

Then you review → approve → assisted-apply:

```bash
python -m src.main daily          # what the 6 AM task runs (also run manually anytime)
python -m src.main review         # INTERACTIVE checklist — tick ✓ to apply, ✗ to skip
python -m src.main report         # static read-only HTML report (alternative to review)
python -m src.main apply          # apply everything already approved (CLI alternative)
python -m src.main status         # tracker stats + recent activity
```

**The `review` checklist** opens a local web page (http://127.0.0.1:5000) listing the
day's top 50 with scores and why-they-fit. For each row:
- **✓ tick** → approves + opens that job pre-filled in a browser for you to submit
- **✗ cross** → skips it

Nothing is applied until you tick it. A background worker applies ticked jobs one at a
time. There's an **Auto-submit** switch at the top: off (default) opens each pre-filled
so you click Submit; on attempts the submit too. GCC job sources: **Apify** (LinkedIn/
Indeed) + your **LinkedIn job-alert emails** (set `GMAIL_APP_PASSWORD`).

### Schedule the 6 AM run (once)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_schedule.ps1
```

This registers a `JobHuntDaily` Windows task at 6:00 AM that runs the pipeline and
pops open the day's report. Manage it with `Get-ScheduledTask -TaskName JobHuntDaily`.

### Assisted apply — one-time browser setup

```bash
.venv/Scripts/python.exe -m playwright install chromium
```

`apply` opens a real browser using a persistent profile in `data/.browser`, so once
you sign in to an ATS (Workday, Greenhouse, LinkedIn…) the login sticks. It pre-fills
name/email/phone and attaches your resume where it can, then **you review and submit** —
nothing is auto-submitted.

### One-off / smaller companies

```bash
python -m src.main run       # single scrape -> score -> tailor -> draft outreach emails
```

- Everything is stored in `data/jobs.db` (SQLite); jobs already seen are never re-processed.
- Daily reports: `data/reports/daily_YYYY-MM-DD.html`. Application packets: `data/applications/`.
- Outreach email drafts (smaller companies that list a contact): `data/drafts/*.eml`.
- Run logs from the scheduled task: `data/logs/`.

## Optional integrations

### Job sources (all free)
The daily pipeline pulls jobs from, in order:
1. **Greenhouse + Lever** company boards — no key. Probes each company in
   `data/companies.xlsx` directly and keeps Bangalore/Hyderabad AI roles.
2. **Adzuna** aggregator — free key from <https://developer.adzuna.com/> (no card).
   Set `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`. Broad India coverage, filtered to your
   company allowlist.
3. **Apify** — optional and now needs a *paid* actor, so it's off unless you set
   `APIFY_TOKEN`.

### Push drafts to Gmail "Drafts"
Set `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (a 16-char Google **App Password**,
not your normal password — <https://myaccount.google.com/apppasswords>). Drafts
then appear in Gmail as well as `data/drafts/`. Leave blank to keep `.eml` only.

## Tuning

In `.env`:
- `JOB_KEYWORDS`, `JOB_LOCATION`, `JOB_REMOTE` — what to search for.
- `MATCH_THRESHOLD` (0–100) — only jobs at/above this get tailored + outreach.
- `MAX_JOBS_PER_RUN` — how many jobs to pull per run.
- `CLAUDE_MODEL` — defaults to `claude-opus-4-8`.

## Project layout

```
src/
  config.py          env-driven settings
  llm.py             Claude API wrapper
  resume_parser.py   resume file -> structured profile.json
  scrapers/          apify_scraper.py + free_scraper.py
  matcher.py         score a job vs. profile
  tailor.py          cover letter + application answers
  contact_finder.py  find hiring-team hints in a posting
  emailer.py         draft outreach (.eml + optional Gmail draft)
  tracker.py         SQLite state (dedupe + records)
  main.py            CLI: parse | run | status
data/
  resume/            drop your resume here
  drafts/            generated .eml outreach drafts
  profile.json       parsed resume
  jobs.db            tracker
```

## Notes on responsible use

- The pipeline never fabricates experience — materials are grounded in your
  resume. Skim them before sending; you're accountable for what goes out.
- Respect each job board's Terms of Service. Prefer official APIs / Apify actors
  over scraping gated pages.
- Cold-emailing hiring managers is drafted, never auto-sent, on purpose.
```
