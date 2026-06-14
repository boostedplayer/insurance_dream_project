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
def confirm_upgrade(payment_link_id: str, holder_id: int, target_policy_id: int, config: RunnableConfig) -> dict:
    """
    Jab user confirm kare ki unhone upgrade payment kar di hai tab is tool ko use karo.
    Payment verify karo, purani policy cancel karo, aur nayi upgraded policy activate karo.

    payment_link_id  — create_upgrade_payment se mila Razorpay link ID.
    holder_id        — jo purana policyholder ID replace ho raha hai.
    target_policy_id — nayi policy ID jisme user upgrade hua hai.
    Returns: nayi policy activation ki details.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        order = conn.execute(
            text("""
                SELECT po.order_id, po.status, po.razorpay_order_id,
                       p.policy_name, p.policy_tenure
                FROM purchase_orders po
                JOIN policy p ON po.policy_id = p.policy_id
                WHERE po.user_id = :uid
                  AND po.razorpay_order_id = :link_id
                  AND po.order_type = 'upgrade'
            """),
            {"uid": auth_user_id, "link_id": payment_link_id}
        ).fetchone()

        if not order:
            order = conn.execute(
                text("""
                    SELECT po.order_id, po.status, po.razorpay_order_id,
                           p.policy_name, p.policy_tenure
                    FROM purchase_orders po
                    JOIN policy p ON po.policy_id = p.policy_id
                    WHERE po.user_id = :uid
                      AND po.status = 'pending'
                      AND po.order_type = 'upgrade'
                    ORDER BY po.created_at DESC LIMIT 1
                """),
                {"uid": auth_user_id}
            ).fetchone()
            if order:
                payment_link_id = dict(order._mapping)["razorpay_order_id"]

    if not order:
        return {
            "status": "no_pending_upgrade",
            "agent_guidance": "No pending upgrade order found. Ask the user to start upgrade flow again."
        }

    order = dict(order._mapping)

    if order["status"] == "completed":
        return {
            "status":      "already_upgraded",
            "policy_name": order["policy_name"],
            "agent_guidance": f"Policy was already upgraded to '{order['policy_name']}'."
        }

    rz_client   = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
    link_data   = rz_client.payment_link.fetch(payment_link_id)
    link_status = link_data.get("status")

    if link_status != "paid":
        return {
            "status":          "payment_pending",
            "razorpay_status": link_status,
            "agent_guidance":  f"Payment not confirmed (status: '{link_status}'). Ask user to complete payment first."
        }

    payment_id = None
    payments   = link_data.get("payments", {}).get("items", [])
    if payments:
        payment_id = payments[0].get("payment_id") or payments[0].get("id")

    today       = date.today()
    tenure      = order["policy_tenure"]
    tenure_days = tenure.days if hasattr(tenure, "days") else 365
    up_to       = today + timedelta(days=tenure_days)
    next_bill   = today + timedelta(days=min(30, tenure_days))

    with engine.begin() as conn:
        # Purani policy cancel kar do
        conn.execute(
            text("""
                UPDATE policyholder
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE holder_id = :hid AND user_id = :uid
            """),
            {"hid": holder_id, "uid": auth_user_id}
        )

        # Upgraded policy ke liye nayi policyholder record bana do
        new_holder = conn.execute(
            text("""
                INSERT INTO policyholder (user_id, policy_id, valid_from, next_bill, up_to, grace_period, status)
                VALUES (:uid, :pid, :vf, :nb, :ut, '30 days', 'active')
                RETURNING holder_id
            """),
            {
                "uid": auth_user_id,
                "pid": target_policy_id,
                "vf":  today,
                "nb":  next_bill,
                "ut":  up_to,
            }
        ).fetchone()

        new_holder_id = new_holder["holder_id"]

        conn.execute(
            text("""
                UPDATE purchase_orders
                SET status = 'completed', razorpay_payment_id = :pay_id, paid_at = CURRENT_TIMESTAMP
                WHERE order_id = :oid
            """),
            {"pay_id": payment_id, "oid": order["order_id"]}
        )

    return {
        "status":         "upgraded",
        "new_holder_id":  new_holder_id,
        "policy_name":    order["policy_name"],
        "valid_from":     str(today),
        "up_to":          str(up_to),
        "next_bill":      str(next_bill),
        "agent_guidance": (
            f"Upgrade successful! Tell the user:\n"
            f"'Your policy has been upgraded to {order['policy_name']}. "
            f"Active from {today} to {up_to}. Next billing date: {next_bill}. "
            "Your old policy has been cancelled. Enjoy your enhanced coverage!'"
        )
    }
