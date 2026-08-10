"""Billing: list plans, view current plan+usage, checkout, confirm, webhook."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Payment, User
from ..plans import DEFAULT_PLAN, PLANS, get_plan
from ..schemas import (
    BillingMe, CheckoutRequest, CheckoutResponse, ConfirmRequest, PlanOut, UsageOut,
)
from ..services import billing, usage

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans():
    return [
        PlanOut(code=p.code, name=p.name, price_inr=p.price_inr,
                runs_per_day=p.runs_per_day, tailors_per_day=p.tailors_per_day,
                scheduling=p.scheduling, features=p.features)
        for p in PLANS.values()
    ]


@router.get("/me", response_model=BillingMe)
def billing_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = get_plan(user.plan)
    return BillingMe(
        plan=plan.code, plan_name=plan.name, plan_expires=user.plan_expires,
        usage=UsageOut(**usage.usage_summary(db, user)),
    )


def _apply_plan(user: User, plan_code: str) -> None:
    now = datetime.now(timezone.utc)
    user.plan = plan_code
    user.plan_since = now
    user.plan_expires = now + timedelta(days=30) if plan_code != DEFAULT_PLAN else None


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    plan = PLANS.get(req.plan_code)
    if plan is None or plan.code == DEFAULT_PLAN or plan.price_paise <= 0:
        raise HTTPException(status_code=400, detail="Not a purchasable plan.")

    order = billing.create_order(plan.price_paise, receipt=f"user{user.id}-{plan.code}")
    db.add(Payment(user_id=user.id, plan_code=plan.code, order_id=order["order_id"],
                   amount_paise=plan.price_paise, status="created", is_mock=order["is_mock"]))
    db.commit()
    return CheckoutResponse(plan_code=plan.code, **order)


@router.post("/confirm", response_model=BillingMe)
def confirm(req: ConfirmRequest, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(
        Payment.user_id == user.id, Payment.order_id == req.order_id
    ).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if payment.status == "paid":
        # idempotent — already applied
        plan = get_plan(user.plan)
        return BillingMe(plan=plan.code, plan_name=plan.name, plan_expires=user.plan_expires,
                         usage=UsageOut(**usage.usage_summary(db, user)))

    if not billing.verify_payment(req.order_id, req.payment_id, req.signature):
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    payment.payment_id = req.payment_id
    payment.status = "paid"
    _apply_plan(user, payment.plan_code)
    db.commit()

    plan = get_plan(user.plan)
    return BillingMe(plan=plan.code, plan_name=plan.name, plan_expires=user.plan_expires,
                     usage=UsageOut(**usage.usage_summary(db, user)))


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay server-to-server confirmation (used in production with live keys)."""
    body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not billing.verify_webhook(body, sig):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    import json

    event = json.loads(body or "{}")
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id", "")
    payment = db.query(Payment).filter(Payment.order_id == order_id).one_or_none()
    if payment and payment.status != "paid":
        payment.payment_id = entity.get("id", "")
        payment.status = "paid"
        user = db.get(User, payment.user_id)
        if user:
            _apply_plan(user, payment.plan_code)
        db.commit()
    return {"ok": True}
