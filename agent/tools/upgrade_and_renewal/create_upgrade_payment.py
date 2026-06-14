import razorpay
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()


@tool
def create_upgrade_payment(holder_id: int, target_policy_id: int, config: RunnableConfig) -> dict:
    """
    Tabhi use karo jab user ne upgrade ke liye haan bol diya ho
    (yaani initiate_upgrade dikhane ke baad user ne yes/confirm/proceed keh diya).
    Naye policy ke poore premium ke liye Razorpay Payment Link banata hai.

    holder_id        — abhi wale policyholder ka ID.
    target_policy_id — jis policy mein upgrade karna hai uska ID (initiate_upgrade se milega).
    Returns: Razorpay payment link URL.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT name, email FROM users WHERE user_id = :uid"),
            {"uid": auth_user_id}
        ).fetchone()

        target = conn.execute(
            text("SELECT policy_name, base_premium, policy_tenure FROM policy WHERE policy_id = :pid"),
            {"pid": target_policy_id}
        ).fetchone()

        underwriting = conn.execute(
            text("""
                SELECT loading_percent FROM underwriting_results
                WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    if not user or not target:
        return {
            "status": "error",
            "agent_guidance": "User or target policy not found. Verify holder_id and target_policy_id."
        }

    user   = dict(user._mapping)
    target = dict(target._mapping)
    uw     = dict(underwriting._mapping) if underwriting else {"loading_percent": 0}

    base_premium  = float(target["base_premium"])
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
        "description": f"Policy Upgrade: {target['policy_name']}",
        "customer":    {"name": user["name"], "email": user["email"]},
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
                    (:uid, :pid, :rz_id, :amount, 'INR', 'pending', 'upgrade')
            """),
            {
                "uid":    auth_user_id,
                "pid":    target_policy_id,
                "rz_id":  razorpay_link_id,
                "amount": amount_paise,
            }
        )

    return {
        "status":           "payment_link_created",
        "payment_link_id":  razorpay_link_id,
        "payment_url":      short_url,
        "amount":           final_premium,
        "currency":         "INR",
        "target_policy":    target["policy_name"],
        "holder_id":        holder_id,
        "target_policy_id": target_policy_id,
        "agent_guidance": (
            f"Share this upgrade payment link: {short_url}\n"
            f"Say: 'Click the link to pay ₹{final_premium} for your upgrade to {target['policy_name']}. "
            "Once paid, come back and I'll activate your new plan immediately!'"
        )
    }
