"""FastAPI application entrypoint.

Run from the backend/ directory:
    uvicorn app.main:app --reload
Interactive API docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import auth, billing, matches, profile, report, schedule
from .services import pipeline
from .services.queue import worker_backend
from .services.scheduler import scheduler_loop

app = FastAPI(title="Job Hunt SaaS API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    global _scheduler_task
    if settings.scheduler_enabled:
        _scheduler_task = asyncio.create_task(scheduler_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _scheduler_task:
        _scheduler_task.cancel()


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "llm_key_configured": pipeline.has_llm_key(),
        "worker": worker_backend(),
        "billing": "mock" if settings.billing_mock else "razorpay",
        "scheduler": settings.scheduler_enabled,
    }


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(matches.router)
app.include_router(report.router)
app.include_router(billing.router)
app.include_router(schedule.router)
