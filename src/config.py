"""Central configuration loaded from environment (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESUME_DIR = DATA_DIR / "resume"
DRAFTS_DIR = DATA_DIR / "drafts"
RAW_DIR = DATA_DIR / "raw"
PROFILE_PATH = DATA_DIR / "profile.json"
DB_PATH = DATA_DIR / "jobs.db"

# Load .env from project root
load_dotenv(ROOT / ".env")


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# --- Claude ---
# The LLM key can be Groq (gsk_...), Anthropic (sk-ant-...), xAI Grok (xai-...),
# or OpenAI (sk-...). We read it from any of these env names (first non-empty).
LLM_API_KEY = (
    os.getenv("GROQ_API_KEY", "").strip()
    or os.getenv("ANTHROPIC_API_KEY", "").strip()
    or os.getenv("XAI_API_KEY", "").strip()
    or os.getenv("OPENAI_API_KEY", "").strip()
)
ANTHROPIC_API_KEY = LLM_API_KEY  # back-compat alias used across the codebase


def _detect_provider(key: str) -> str:
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("xai-"):
        return "xai"
    return "openai"


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower() or _detect_provider(LLM_API_KEY)

# Per-provider default model (override with LLM_MODEL in .env).
_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-opus-4-8",
    "xai": "grok-2-latest",
    "openai": "gpt-4o",
}
LLM_MODEL = (
    os.getenv("LLM_MODEL", "").strip()
    or os.getenv("CLAUDE_MODEL", "").strip()
    or _DEFAULT_MODELS.get(LLM_PROVIDER, "llama-3.3-70b-versatile")
)
# If the user left CLAUDE_MODEL=claude-opus-4-8 but the key isn't Anthropic,
# fall back to the provider default so we don't send a Claude id to Groq.
if LLM_PROVIDER != "anthropic" and LLM_MODEL.startswith("claude"):
    LLM_MODEL = _DEFAULT_MODELS[LLM_PROVIDER]
CLAUDE_MODEL = LLM_MODEL  # back-compat alias

# --- Apify (optional; default actor is paid) ---
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "").strip()
APIFY_JOBS_ACTOR = os.getenv("APIFY_JOBS_ACTOR", "bebity/linkedin-jobs-scraper").strip()

# --- Adzuna (free job API; https://developer.adzuna.com/) ---
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()

# --- Search preferences ---
JOB_KEYWORDS = _split(os.getenv("JOB_KEYWORDS", "Python Developer"))
# JOB_LOCATION may be a single value or a comma-separated list (e.g. "Bangalore, Hyderabad").
JOB_LOCATION = os.getenv("JOB_LOCATION", "India").strip()
JOB_LOCATIONS = _split(JOB_LOCATION) or ["India"]
JOB_REMOTE = os.getenv("JOB_REMOTE", "true").strip().lower() in ("1", "true", "yes")
MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "70"))
MAX_JOBS_PER_RUN = int(os.getenv("MAX_JOBS_PER_RUN", "25"))

# --- Applicant contact ---
FULL_NAME = os.getenv("FULL_NAME", "").strip()
EMAIL = os.getenv("EMAIL", "").strip()
PHONE = os.getenv("PHONE", "").strip()
LINKEDIN_URL = os.getenv("LINKEDIN_URL", "").strip()
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "").strip()
GITHUB_URL = os.getenv("GITHUB_URL", "").strip()

# --- Email ---
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()


def applicant_contact() -> dict:
    """Contact block used to fill applications and sign outreach emails."""
    return {
        "full_name": FULL_NAME,
        "email": EMAIL,
        "phone": PHONE,
        "linkedin": LINKEDIN_URL,
        "portfolio": PORTFOLIO_URL,
        "github": GITHUB_URL,
    }


def require_llm() -> None:
    if not LLM_API_KEY:
        raise SystemExit(
            "No LLM API key set. Add GROQ_API_KEY (or ANTHROPIC_API_KEY) to .env."
        )


# back-compat alias
require_anthropic = require_llm
