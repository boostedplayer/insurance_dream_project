import razorpay
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()


@tool
def create_payment_order(policy_id: int, config: RunnableConfig) -> dict:
    """
    Tabhi use karo jab user ne purchase ke liye haan bol diya ho
    (yaani initiate_purchase dikhane ke baad user ne yes/proceed/confirm/buy keh diya ho).
    Razorpay Payment Link banata hai aur user ko pay karne ka URL return karta hai.

    policy_id — woh numeric policy ID jo initiate_purchase ne return ki thi.
    Ek payment link URL return karta hai jis par click karke user payment complete kare.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT name, email FROM users WHERE user_id = :uid"),
            {"uid": auth_user_id}
        ).fetchone()

        policy = conn.execute(
            text("SELECT policy_name, base_premium FROM policy WHERE policy_id = :pid"),
            {"pid": policy_id}
        ).fetchone()

        underwriting = conn.execute(
            text("""
                SELECT loading_percent
                FROM underwriting_results
                WHERE user_id = :uid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    if not user or not policy:
        return {
            "status": "error",
            "agent_guidance": "User or policy record not found. Ask the user to clarify."
        }

    user   = dict(user._mapping)
    policy = dict(policy._mapping)
    uw     = dict(underwriting._mapping) if underwriting else {"loading_percent": 0}

    base_premium  = float(policy["base_premium"])
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
        "description": f"Insurance Policy: {policy['policy_name']}",
        "customer": {
            "name":  user["name"],
            "email": user["email"],
        },
        "notify":          {"email": True},
        "callback_url":    os.getenv("RAZORPAY_CALLBACK_URL", "https://yourdomain.com/payment/success"),
        "callback_method": "get",
    })

    razorpay_link_id = link_data["id"]
    short_url        = link_data["short_url"]

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO purchase_orders
                    (user_id, policy_id, razorpay_order_id, amount_paise, currency, status)
                VALUES
                    (:uid, :pid, :rz_id, :amount, 'INR', 'pending')
            """),
            {
                "uid":    auth_user_id,
                "pid":    policy_id,
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
        "policy_name":     policy["policy_name"],
        "agent_guidance": (
            f"Share the link with the user: {short_url}\n"
            f"Say: 'Click the link to complete your ₹{final_premium} payment securely via Razorpay. "
            "Once you've paid, come back and let me know — I'll activate your policy instantly!'\n"
            "Remember the payment_link_id for when the user returns to confirm payment."
        )
    }
