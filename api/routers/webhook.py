import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from agent.db.db import engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/webhook", tags=["webhook"])

WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")


def _verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    """
    called by Razorpay after payment. verifies signature and updates purchase_orders status.
    register this URL in Razorpay dashboard → Webhooks.
    """
    body      = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if WEBHOOK_SECRET and not _verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = await request.json()

    event_type = event.get("event")

    if event_type == "payment_link.paid":
        payload     = event.get("payload", {})
        link_entity = payload.get("payment_link", {}).get("entity", {})
        pay_entity  = payload.get("payment", {}).get("entity", {})

        link_id    = link_entity.get("id")
        payment_id = pay_entity.get("id")

        if link_id:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE purchase_orders
                        SET status = 'completed',
                            razorpay_payment_id = :pay_id,
                            paid_at = CURRENT_TIMESTAMP
                        WHERE razorpay_order_id = :link_id
                          AND status = 'pending'
                    """),
                    {"pay_id": payment_id, "link_id": link_id}
                )

    elif event_type == "payment_link.expired":
        payload = event.get("payload", {})
        link_id = payload.get("payment_link", {}).get("entity", {}).get("id")
        if link_id:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE purchase_orders
                        SET status = 'expired'
                        WHERE razorpay_order_id = :link_id AND status = 'pending'
                    """),
                    {"link_id": link_id}
                )

    return {"status": "ok"}
