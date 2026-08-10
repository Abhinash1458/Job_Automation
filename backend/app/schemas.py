"""Pydantic request/response models (the API contract)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Profile ---
class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resume_filename: str
    updated_at: datetime | None = None
    data: dict


# --- Matching ---
class MatchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    keywords: str
    location: str
    total: int
    scored: int
    error: str
    created_at: datetime
    finished_at: datetime | None = None


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    title: str
    company: str
    location: str
    source: str
    score: int
    verdict: str
    reasons: list[str]
    missing: list[str]
    status: str


class QA(BaseModel):
    question: str
    answer: str


class Factor(BaseModel):
    factor: str
    score: int
    weight: float
    detail: str


class MatchDetail(MatchOut):
    """Full match view including the posting text, engine breakdown, and packet."""
    description: str = ""
    breakdown: list[Factor] = []
    cover_letter: str = ""
    pitch: str = ""
    answers: list[QA] = []


class RunRequest(BaseModel):
    """Optional overrides; falls back to the user's profile / project defaults."""
    keywords: list[str] | None = None
    location: str | None = None
    limit: int | None = None
    company_type: str = "any"  # any | gcc | product | startup | service
    job_type: str = "any"      # any | full_time | contract | remote


class SegmentOptions(BaseModel):
    company_types: list[str]
    job_types: list[str]


# --- Career report (own, derived from the user's profile + matches) ---
class ReportSkillBar(BaseModel):
    label: str
    value: int  # 0-100


class CareerReport(BaseModel):
    headline: str
    years_experience: float
    readiness: int                 # 0-100 overall readiness score
    readiness_label: str
    strengths: list[str]           # top skills
    focus_areas: list[str]         # aggregated gaps from scored matches
    target_roles: list[str]
    skill_bars: list[ReportSkillBar]
    matches_analyzed: int
    strong_matches: int            # score >= 85
    avg_score: int
    top_companies: list[str]


# --- Phase 3: billing + usage + scheduling ---
class PlanOut(BaseModel):
    code: str
    name: str
    price_inr: int
    runs_per_day: int
    tailors_per_day: int
    scheduling: bool
    features: list[str]


class UsageOut(BaseModel):
    plan: str
    plan_name: str
    runs_used: int
    runs_limit: int
    tailors_used: int
    tailors_limit: int
    scheduling: bool


class BillingMe(BaseModel):
    plan: str
    plan_name: str
    plan_expires: datetime | None = None
    usage: UsageOut


class CheckoutRequest(BaseModel):
    plan_code: str


class CheckoutResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    is_mock: bool
    plan_code: str


class ConfirmRequest(BaseModel):
    order_id: str
    payment_id: str = "mock_payment"
    signature: str = "mock_signature"


class ScheduleOut(BaseModel):
    enabled: bool
    hour_utc: int
    last_run_date: str
    scheduling_allowed: bool


class ScheduleUpdate(BaseModel):
    enabled: bool
    hour_utc: int = Field(ge=0, le=23)
