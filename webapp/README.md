# Job Hunt — Web App (Phase 1)

Turns the single-user CLI pipeline in [`src/`](../src) into a **multi-user web
product**: sign up → upload your CV → get scored job matches in a browser.

This is **Phase 1** (the SaaS skeleton). It reuses your existing scraping,
resume-parsing, and scoring code — it does **not** reimplement any of it. The
business logic still lives in `src/`; the backend imports it via
`backend/app/services/pipeline.py`.

```
Next.js frontend  ──HTTP──►  FastAPI backend  ──imports──►  src/ pipeline
(login, CV upload,           (auth, per-user DB,            (scrape_jobs,
 dashboard)                   background matching)           matcher, resume_parser)
```

## Architecture

| Piece | Location | What it does |
|---|---|---|
| **Backend API** | [`backend/app`](../backend/app) | FastAPI: JWT auth, per-user profiles, background match runs |
| **Pipeline wrapper** | `backend/app/services/pipeline.py` | Multi-user-safe adapter over `src/` (no global `profile.json`) |
| **Background runner** | `backend/app/services/runner.py` | Runs scrape + score off the request thread; writes results to DB |
| **Database** | SQLAlchemy models | SQLite by default; point `DATABASE_URL` at Postgres for hosting |
| **Frontend** | [`frontend`](../frontend) | Next.js + Tailwind: login/register, CV upload, dashboard with polling |

Data model: `users` → one `profiles` (parsed CV) → many `match_runs` → many
`matches`. This replaces the CLI's single global `profile.json` + `jobs.db`.

## Run it locally

**1. Backend** (uses the project's existing `.venv`):

```bash
# from the repo root
cp backend/.env.example backend/.env        # edit JWT_SECRET; SQLite works as-is
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd backend
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- LLM + scraper keys are read from the **project-root `.env`** (the same
  `GROQ_API_KEY` / `ANTHROPIC_API_KEY` etc. the CLI already uses). You do not
  duplicate them in `backend/.env`.

**2. Frontend:**

```bash
cd frontend
cp .env.local.example .env.local            # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open <http://localhost:3000>, register, upload a CV, click **Find matches**.

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` · `/auth/login` · GET `/auth/me` | Auth (JWT) |
| GET/POST | `/profile` · `/profile/upload` | Parsed CV profile |
| POST | `/matches/run` | Start a background match run (usage-limited) |
| GET | `/matches` · `/matches/runs/latest` · `/matches/runs/{id}` · `/matches/runs/{id}/results` | Matches & runs |
| GET/POST/PATCH | `/matches/{id}` · `/matches/{id}/tailor` · `/matches/{id}?status=` | Detail, tailor packet, save/skip/applied |
| GET | `/report` | Career readiness report |
| GET | `/billing/plans` · `/billing/me` | Plans & current subscription/usage |
| POST | `/billing/checkout` · `/billing/confirm` · `/billing/webhook` | Razorpay upgrade flow (mock without keys) |
| GET/PUT | `/schedule` · POST `/schedule/run-now` | Per-user scheduled daily runs (Pro) |

## Phase 3 — SaaS operations (done)

- **Billing tiers** ([`plans.py`](../backend/app/plans.py)): **Free** (2 runs + 3 packets/day) and
  **Pro ₹499/mo** (25 runs + 50 packets/day + scheduling). Limits enforced in
  the API (HTTP **402** with an upgrade prompt when exceeded).
- **Razorpay billing** ([`services/billing.py`](../backend/app/services/billing.py)) with a **mock mode**:
  without live keys the upgrade flow issues a fake order and auto-confirms, so
  the whole tier system is testable locally.
- **Worker queue** ([`services/queue.py`](../backend/app/services/queue.py)): RQ + Redis when `REDIS_URL`
  is set (run `python worker.py`), else an in-process thread. Same job either way.
- **Per-user scheduled runs** ([`services/scheduler.py`](../backend/app/services/scheduler.py)): an in-app
  asyncio loop triggers each Pro user's daily match at their chosen UTC hour.
- **Postgres + Alembic** ([`migrations/`](../backend/migrations)): set `DATABASE_URL` to Postgres and
  run `alembic upgrade head`. SQLite remains the zero-setup dev default.
- **Deployment**: [`backend/Dockerfile`](../backend/Dockerfile), [`frontend/Dockerfile`](../frontend/Dockerfile),
  [`docker-compose.yml`](../docker-compose.yml) (Postgres + Redis + API + worker + web),
  [`render.yaml`](../render.yaml) blueprint, and a [`Procfile`](../backend/Procfile).

### Run the full stack (Docker)

```bash
docker compose up --build     # Postgres + Redis + API + worker + frontend
# LLM keys come from the repo-root .env; billing runs in mock mode unless
# RAZORPAY_KEY_ID/_SECRET are set.
```

### Go-live checklist (needs real accounts)

- Set `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (+ webhook secret) for live payments.
- Point `DATABASE_URL` at managed Postgres; run `alembic upgrade head`.
- Set `REDIS_URL` and run the `worker` process for scalable job execution.
- Set a strong `JWT_SECRET` and the deployed frontend origin in `CORS_ORIGINS`.

## Still deferred (future)

- Managed auth (Supabase/Clerk) as an alternative to the built-in JWT.
- Annual plans, coupons, student discounts, invoices.
- Email notifications when scheduled runs finish.

## IP / licensing notes

- All UI copy, visual design, and any company/salary datasets here are your own
  — no third-party product's wording, branding, or proprietary data is used.
- The Workday/ATS JSON technique in `src/scrapers/` uses public endpoints; keep
  the human-in-the-loop, no-auto-submit design to respect ATS Terms of Service.
- If you later port any MIT-licensed code (e.g. from `career-ops`), add its
  license + copyright under a `LICENSES/` folder.
