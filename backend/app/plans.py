"""Subscription tiers and their limits (single source of truth).

Prices are in paise (INR minor units) for Razorpay. Limits are per-UTC-day.
`-1` means unlimited.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_paise: int          # per month, in paise (₹1 = 100 paise)
    runs_per_day: int         # match runs allowed per day (-1 = unlimited)
    tailors_per_day: int      # tailored packets per day (-1 = unlimited)
    scheduling: bool          # can enable per-user scheduled daily runs
    features: list[str] = field(default_factory=list)

    @property
    def price_inr(self) -> int:
        return self.price_paise // 100


PLANS: dict[str, Plan] = {
    "free": Plan(
        code="free", name="Free", price_paise=0,
        runs_per_day=2, tailors_per_day=3, scheduling=False,
        features=[
            "2 job-match runs per day",
            "3 tailored packets per day",
            "Career readiness report",
            "Application tracker",
        ],
    ),
    "pro": Plan(
        code="pro", name="Pro", price_paise=49900,  # ₹499/mo
        runs_per_day=25, tailors_per_day=50, scheduling=True,
        features=[
            "25 job-match runs per day",
            "50 tailored packets per day",
            "Automated daily scheduled runs",
            "Everything in Free",
        ],
    ),
}

DEFAULT_PLAN = "free"


def get_plan(code: str | None) -> Plan:
    return PLANS.get(code or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])
