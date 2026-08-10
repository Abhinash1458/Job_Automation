"""Razorpay billing with a transparent MOCK fallback.

When live keys are configured (RAZORPAY_KEY_ID / _SECRET) real orders are created
and signatures verified. Without keys, `settings.billing_mock` is True and the
provider issues fake orders + auto-verifies, so the full tier/upgrade flow is
testable end-to-end locally without a gateway account.
"""
from __future__ import annotations

import uuid

from ..config import settings


def create_order(amount_paise: int, receipt: str) -> dict:
    """Create a payment order. Returns fields the frontend checkout needs."""
    if settings.billing_mock:
        return {
            "order_id": f"order_mock_{uuid.uuid4().hex[:16]}",
            "amount": amount_paise,
            "currency": "INR",
            "key_id": "mock",
            "is_mock": True,
        }
    import razorpay

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
    })
    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.razorpay_key_id,
        "is_mock": False,
    }


def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify a completed payment's signature. Mock mode always succeeds."""
    if settings.billing_mock:
        return True
    import razorpay

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except Exception:  # noqa: BLE001 - signature mismatch / SDK error
        return False


def verify_webhook(body: bytes, signature: str) -> bool:
    if settings.billing_mock or not settings.razorpay_webhook_secret:
        return False
    import razorpay

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    try:
        client.utility.verify_webhook_signature(
            body.decode("utf-8"), signature, settings.razorpay_webhook_secret
        )
        return True
    except Exception:  # noqa: BLE001
        return False
