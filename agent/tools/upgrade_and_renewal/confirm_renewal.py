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
def confirm_renewal(payment_link_id: str, config: RunnableConfig) -> dict:
    """
    use when user says they've completed renewal payment.
    verifies payment and extends policy validity to the next tenure.
    payment_link_id: the razorpay link id returned by create_renewal_payment.
    returns updated policy expiry dates.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        order = conn.execute(
            text("""
                SELECT po.order_id, po.policy_id, po.status, po.razorpay_order_id,
                       ph.holder_id, ph.up_to,
                       p.policy_name, p.policy_tenure
                FROM purchase_orders po
                JOIN policy p ON po.policy_id = p.policy_id
                LEFT JOIN policyholder ph
                    ON ph.policy_id = po.policy_id AND ph.user_id = po.user_id AND ph.status = 'active'
                WHERE po.user_id = :uid
                  AND po.razorpay_order_id = :link_id
                  AND po.order_type = 'renewal'
            """),
            {"uid": auth_user_id, "link_id": payment_link_id}
        ).fetchone()

        if not order:
            # fallback: find the latest pending renewal order
            order = conn.execute(
                text("""
                    SELECT po.order_id, po.policy_id, po.status, po.razorpay_order_id,
                           ph.holder_id, ph.up_to,
                           p.policy_name, p.policy_tenure
                    FROM purchase_orders po
                    JOIN policy p ON po.policy_id = p.policy_id
                    LEFT JOIN policyholder ph
                        ON ph.policy_id = po.policy_id AND ph.user_id = po.user_id AND ph.status = 'active'
                    WHERE po.user_id = :uid
                      AND po.status = 'pending'
                      AND po.order_type = 'renewal'
                    ORDER BY po.created_at DESC LIMIT 1
                """),
                {"uid": auth_user_id}
            ).fetchone()
            if order:
                payment_link_id = dict(order._mapping)["razorpay_order_id"]

    if not order:
        return {
            "status": "no_pending_renewal",
            "agent_guidance": "No pending renewal order found. Ask user to start renewal via get_renewal_summary first."
        }

    order = dict(order._mapping)

    if order["status"] == "completed":
        return {
            "status":      "already_renewed",
            "policy_name": order["policy_name"],
            "agent_guidance": f"Policy '{order['policy_name']}' was already renewed."
        }

    rz_client   = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
    link_data   = rz_client.payment_link.fetch(payment_link_id)
    link_status = link_data.get("status")

    if link_status != "paid":
        return {
            "status":          "payment_pending",
            "razorpay_status": link_status,
            "agent_guidance":  f"Payment not confirmed yet (status: '{link_status}'). Ask user to complete payment first."
        }

    payment_id = None
    payments   = link_data.get("payments", {}).get("items", [])
    if payments:
        payment_id = payments[0].get("payment_id") or payments[0].get("id")

    # new validity starts the day after old up_to for seamless continuation
    old_up_to    = order["up_to"] if order["up_to"] else date.today()
    tenure       = order["policy_tenure"]
    tenure_days  = tenure.days if hasattr(tenure, "days") else 365
    new_valid_from = old_up_to + timedelta(days=1) if hasattr(old_up_to, '__add__') else date.today()
    new_up_to      = new_valid_from + timedelta(days=tenure_days)
    new_next_bill  = new_valid_from + timedelta(days=min(30, tenure_days))

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE policyholder
                SET valid_from = :vf, up_to = :ut, next_bill = :nb
                WHERE holder_id = :hid
            """),
            {
                "vf":  new_valid_from,
                "ut":  new_up_to,
                "nb":  new_next_bill,
                "hid": order["holder_id"],
            }
        )
        conn.execute(
            text("""
                UPDATE purchase_orders
                SET status = 'completed', razorpay_payment_id = :pay_id, paid_at = CURRENT_TIMESTAMP
                WHERE order_id = :oid
            """),
            {"pay_id": payment_id, "oid": order["order_id"]}
        )

    return {
        "status":        "renewed",
        "policy_name":   order["policy_name"],
        "new_valid_from": str(new_valid_from),
        "new_up_to":      str(new_up_to),
        "new_next_bill":  str(new_next_bill),
        "agent_guidance": (
            f"Policy renewed! Tell the user:\n"
            f"'Your {order['policy_name']} has been renewed successfully. "
            f"New validity: {new_valid_from} to {new_up_to}. "
            f"Next billing date: {new_next_bill}. You're fully covered!'"
        )
    }
