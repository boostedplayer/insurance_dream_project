import razorpay
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
from datetime import date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()


@tool
def confirm_purchase(payment_link_id: str, config: RunnableConfig) -> dict:
    """
    Jab user bol de ki usne payment kar di
    ('I've paid', 'payment done', 'I completed it', 'activate my policy', 'check my payment'),
    tab is tool ko use karo.
    Razorpay payment verify karo aur confirm hone par policy activate kar do.

    payment_link_id — create_payment_order ne jo Razorpay payment link ID di thi.
                      Agar user ne mention nahi ki toh conversation history se dhundh lo.
    Returns: policy activation confirmation ya current payment status.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        order = conn.execute(
            text("""
                SELECT po.order_id, po.policy_id, po.amount_paise, po.status,
                       po.razorpay_order_id,
                       p.policy_name, p.policy_tenure
                FROM purchase_orders po
                JOIN policy p ON po.policy_id = p.policy_id
                WHERE po.user_id = :uid AND po.razorpay_order_id = :link_id
            """),
            {"uid": auth_user_id, "link_id": payment_link_id}
        ).fetchone()

        # Fallback: agar LLM galat ya khaali ID de, toh latest pending order dhundho
        if not order:
            order = conn.execute(
                text("""
                    SELECT po.order_id, po.policy_id, po.amount_paise, po.status,
                           po.razorpay_order_id,
                           p.policy_name, p.policy_tenure
                    FROM purchase_orders po
                    JOIN policy p ON po.policy_id = p.policy_id
                    WHERE po.user_id = :uid AND po.status = 'pending'
                    ORDER BY po.created_at DESC LIMIT 1
                """),
                {"uid": auth_user_id}
            ).fetchone()

            if order:
                payment_link_id = dict(order._mapping)["razorpay_order_id"]

    if not order:
        return {
            "status": "no_pending_order",
            "agent_guidance": "No pending payment order found. Ask the user to initiate a purchase first."
        }

    order = dict(order._mapping)

    if order["status"] == "completed":
        return {
            "status":      "already_activated",
            "policy_name": order["policy_name"],
            "agent_guidance": f"Policy '{order['policy_name']}' is already active for this user."
        }

    rz_client = razorpay.Client(auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET"),
    ))

    link_data   = rz_client.payment_link.fetch(payment_link_id)
    link_status = link_data.get("status")

    if link_status != "paid":
        return {
            "status":           "payment_pending",
            "razorpay_status":  link_status,
            "agent_guidance": (
                f"Payment not confirmed yet (Razorpay status: '{link_status}'). "
                "Ask the user to complete payment via the link shared earlier, then check again."
            )
        }

    # Razorpay payment link response se payment_id nikaal lo
    payment_id = None
    payments   = link_data.get("payments", {}).get("items", [])
    if payments:
        payment_id = payments[0].get("payment_id") or payments[0].get("id")

    # Tenure se policy validity dates calculate karo (PostgreSQL INTERVAL → timedelta)
    today      = date.today()
    valid_from = today
    tenure     = order["policy_tenure"]

    tenure_days = tenure.days if hasattr(tenure, "days") else 365
    up_to       = valid_from + timedelta(days=tenure_days)
    # Start se 30 din baad ka next bill (ya agar tenure 30 din se kam ho toh up_to pe)
    next_bill   = valid_from + timedelta(days=min(30, tenure_days))

    with engine.begin() as conn:
        holder = conn.execute(
            text("""
                INSERT INTO policyholder (user_id, policy_id, valid_from, next_bill, up_to, grace_period)
                VALUES (:uid, :pid, :vf, :nb, :ut, '30 days')
                RETURNING holder_id
            """),
            {
                "uid": auth_user_id,
                "pid": order["policy_id"],
                "vf":  valid_from,
                "nb":  next_bill,
                "ut":  up_to,
            }
        ).fetchone()

        holder_id = holder["holder_id"]

        conn.execute(
            text("""
                UPDATE purchase_orders
                SET status = 'completed',
                    razorpay_payment_id = :pay_id,
                    paid_at = CURRENT_TIMESTAMP
                WHERE order_id = :oid
            """),
            {"pay_id": payment_id, "oid": order["order_id"]}
        )

    return {
        "status":      "activated",
        "holder_id":   holder_id,
        "policy_name": order["policy_name"],
        "valid_from":  str(valid_from),
        "up_to":       str(up_to),
        "next_bill":   str(next_bill),
        "agent_guidance": (
            f"Policy activated! Tell the user:\n"
            f"'Your {order['policy_name']} is now active from {valid_from} to {up_to}. "
            f"Your next billing date is {next_bill}. "
            "A confirmation has been sent to your registered email. You're now fully covered!'"
        )
    }
