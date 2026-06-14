from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def initiate_purchase(policy_name: str, config: RunnableConfig) -> dict:
    """
    Jab user ne decide kar liya ho ki woh kaunsi insurance policy khareedna chahta hai, tab use karo.
    Payment order banane se PEHLE yeh call karo — yeh user ka personalized
    premium fetch karta hai aur ek poora purchase summary dikhata hai confirm karne ke liye.

    Examples: 'I want to buy SecureHealth Plus', 'I'll take the motor policy',
              'buy this policy for me', 'proceed with purchase of this plan'.

    policy_name — us policy ka naam jo user chahta hai (jo pehle conversation mein aaya ho).
    Returns policy details, risk-adjusted premium breakdown, aur aage ka guidance.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        policy = conn.execute(
            text("""
                SELECT policy_id, policy_name, policy_type, policy_description,
                       base_premium, coverage_amount, policy_tenure,
                       what_covers, what_doesnt_cover
                FROM policy
                WHERE LOWER(policy_name) LIKE LOWER(:name)
                LIMIT 1
            """),
            {"name": f"%{policy_name}%"}
        ).fetchone()

        if not policy:
            return {
                "status": "policy_not_found",
                "agent_guidance": (
                    f"No policy found matching '{policy_name}'. "
                    "Ask the user to clarify the name, or call new_policy_inquiry to show options."
                )
            }

        policy     = dict(policy._mapping)
        policy_id  = policy["policy_id"]

        # Pehle is exact policy ke liye underwriting record dhundo, phir user ke kisi bhi record se
        underwriting = conn.execute(
            text("""
                SELECT risk_category, loading_percent, risk_score
                FROM underwriting_results
                WHERE user_id = :uid AND policy_id = :pid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id, "pid": policy_id}
        ).fetchone()

        if not underwriting:
            underwriting = conn.execute(
                text("""
                    SELECT risk_category, loading_percent, risk_score
                    FROM underwriting_results
                    WHERE user_id = :uid
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"uid": auth_user_id}
            ).fetchone()

    if not underwriting:
        return {
            "status": "no_underwriting",
            "policy": {
                "policy_id":      policy_id,
                "policy_name":    policy["policy_name"],
                "policy_type":    policy["policy_type"],
                "base_premium":   str(policy["base_premium"]),
                "coverage_amount": str(policy["coverage_amount"]),
            },
            "agent_guidance": (
                "User has not been risk-assessed yet. Tell them their personalized premium "
                "requires a risk assessment first. Suggest describing their insurance needs "
                "so you can run new_policy_inquiry."
            )
        }

    uw             = dict(underwriting._mapping)
    base_premium   = float(policy["base_premium"])
    loading_pct    = float(uw["loading_percent"])
    loading_amount = round(base_premium * loading_pct / 100, 2)
    final_premium  = round(base_premium + loading_amount, 2)

    return {
        "status":    "ready_for_purchase",
        "policy_id": policy_id,
        "policy": {
            "policy_name":        policy["policy_name"],
            "policy_type":        policy["policy_type"],
            "policy_description": policy["policy_description"],
            "coverage_amount":    str(policy["coverage_amount"]),
            "policy_tenure":      str(policy["policy_tenure"]),
            "what_covers":        policy["what_covers"],
            "what_doesnt_cover":  policy["what_doesnt_cover"],
        },
        "pricing": {
            "base_premium":    base_premium,
            "risk_category":   uw["risk_category"],
            "risk_score":      uw["risk_score"],
            "loading_percent": loading_pct,
            "loading_amount":  loading_amount,
            "final_premium":   final_premium,
            "currency":        "INR",
        },
        "agent_guidance": (
            "Show the user a clear purchase summary:\n"
            f"  Policy:   {policy['policy_name']} ({policy['policy_type']})\n"
            f"  Coverage: ₹{policy['coverage_amount']}\n"
            f"  Tenure:   {policy['policy_tenure']}\n"
            f"  Base premium:    ₹{base_premium}\n"
            f"  Risk loading:    {loading_pct}% = ₹{loading_amount}  (your risk category: {uw['risk_category']})\n"
            f"  Final premium:   ₹{final_premium} per period\n\n"
            "Then ask: 'Would you like to proceed to payment?' "
            "If yes, call create_payment_order with policy_id."
        )
    }
