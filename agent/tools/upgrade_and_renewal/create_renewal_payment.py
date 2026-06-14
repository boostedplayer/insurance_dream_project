import razorpay
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()


@tool
def create_renewal_payment(holder_id: int, config: RunnableConfig) -> dict:
    """
    Jab user confirm kar de ki woh renew karna chahta hai tab hi use karo (get_renewal_summary
    dikhane ke baad aur user ne yes/proceed/renew bol diya ho). Renewal amount ke liye
    ek Razorpay Payment Link banata hai.

    holder_id — woh policyholder ID jo get_renewal_summary ne return ki thi.
    Returns: Razorpay payment link URL jis par user click karke pay karta hai.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT ph.holder_id, p.policy_id, p.policy_name, p.base_premium,
                       u.name, u.email
                FROM policyholder ph
                JOIN policy p  ON ph.policy_id  = p.policy_id
                JOIN users u   ON ph.user_id     = u.user_id
                WHERE ph.holder_id = :hid AND ph.user_id = :uid AND ph.status = 'active'
            """),
            {"hid": holder_id, "uid": auth_user_id}
        ).fetchone()

        if not row:
            return {
                "status": "error",
                "agent_guidance": "Policy holder record not found or already cancelled. Ask user to confirm."
            }

        row = dict(row._mapping)

        underwriting = conn.execute(
            text("""
                SELECT loading_percent FROM underwriting_results
                WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    uw            = dict(underwriting._mapping) if underwriting else {"loading_percent": 0}
    base_premium  = float(row["base_premium"])
    loading_pct   = float(uw["loading_percent"])
    final_premium = round(base_premium + base_premium * loading_pct / 100, 2)
    amount_paise  = int(final_premium * 100)

    rz_client = razorpay.Client(auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET"),
    ))

    link_data = rz_client.payment_link.create({
        "amount":      amount_paise,
        "currency":    "INR",
        "description": f"Policy Renewal: {row['policy_name']}",
        "customer":    {"name": row["name"], "email": row["email"]},
        "notify":      {"email": True},
        "callback_url":    os.getenv("RAZORPAY_CALLBACK_URL", "https://yourdomain.com/payment/success"),
        "callback_method": "get",
    })

    razorpay_link_id = link_data["id"]
    short_url        = link_data["short_url"]

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO purchase_orders
                    (user_id, policy_id, razorpay_order_id, amount_paise, currency, status, order_type)
                VALUES
                    (:uid, :pid, :rz_id, :amount, 'INR', 'pending', 'renewal')
            """),
            {
                "uid":    auth_user_id,
                "pid":    row["policy_id"],
                "rz_id":  razorpay_link_id,
                "amount": amount_paise,
            }
        )

    return {
        "status":          "payment_link_created",
        "payment_link_id": razorpay_link_id,
        "payment_url":     short_url,
        "amount":          final_premium,
        "currency":        "INR",
        "policy_name":     row["policy_name"],
        "agent_guidance": (
            f"Share this renewal payment link: {short_url}\n"
            f"Say: 'Click the link to pay ₹{final_premium} for your renewal. "
            "Once done, come back and let me know — I'll extend your policy instantly!'"
        )
    }
