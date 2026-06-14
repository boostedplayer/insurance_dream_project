from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def initiate_upgrade(holder_id: int, target_policy_name: str, config: RunnableConfig) -> dict:
    """
    Jab user ne decide kar liya ho ki kaun si policy chahiye upgrade ke liye,
    tab is tool ko call karo (yani get_upgrade_options dikha diya gaya ho aur user ne ek choose kar liya ho).
    Ye payment se pehle poora upgrade summary dikhata hai — nayi premium ke saath.

    holder_id          — abhi ka policyholder ID.
    target_policy_name — jo policy user upgrade karna chahta hai uska naam.
    Returns: upgrade ka summary jisme purani aur nayi premium compare hogi, aur agle steps bhi.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        current = conn.execute(
            text("""
                SELECT ph.holder_id, p.policy_id, p.policy_name, p.base_premium,
                       p.coverage_amount, p.policy_type
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.holder_id = :hid AND ph.user_id = :uid AND ph.status = 'active'
            """),
            {"hid": holder_id, "uid": auth_user_id}
        ).fetchone()

        if not current:
            return {
                "status": "not_found",
                "agent_guidance": "Active policyholder record not found. Verify holder_id."
            }

        target = conn.execute(
            text("""
                SELECT policy_id, policy_name, policy_type, base_premium,
                       coverage_amount, policy_tenure, what_covers, what_doesnt_cover
                FROM policy
                WHERE LOWER(policy_name) LIKE LOWER(:name)
                LIMIT 1
            """),
            {"name": f"%{target_policy_name}%"}
        ).fetchone()

        if not target:
            return {
                "status": "target_not_found",
                "agent_guidance": (
                    f"Target policy '{target_policy_name}' not found. "
                    "Ask the user to pick from the options shown by get_upgrade_options."
                )
            }

        underwriting = conn.execute(
            text("""
                SELECT loading_percent, risk_category, risk_score
                FROM underwriting_results
                WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    current = dict(current._mapping)
    target  = dict(target._mapping)
    uw      = dict(underwriting._mapping) if underwriting else {"loading_percent": 0, "risk_category": "unknown", "risk_score": None}

    loading_pct = float(uw["loading_percent"])

    old_base     = float(current["base_premium"])
    old_final    = round(old_base + old_base * loading_pct / 100, 2)

    new_base     = float(target["base_premium"])
    new_loading  = round(new_base * loading_pct / 100, 2)
    new_final    = round(new_base + new_loading, 2)

    premium_diff = round(new_final - old_final, 2)

    return {
        "status":           "ready_for_upgrade",
        "holder_id":        holder_id,
        "target_policy_id": target["policy_id"],
        "current_policy": {
            "policy_name":     current["policy_name"],
            "coverage_amount": str(current["coverage_amount"]),
            "final_premium":   old_final,
        },
        "target_policy": {
            "policy_id":        target["policy_id"],
            "policy_name":      target["policy_name"],
            "coverage_amount":  str(target["coverage_amount"]),
            "policy_tenure":    str(target["policy_tenure"]),
            "what_covers":      target["what_covers"],
            "what_doesnt_cover": target["what_doesnt_cover"],
            "base_premium":     new_base,
            "loading_percent":  loading_pct,
            "loading_amount":   new_loading,
            "final_premium":    new_final,
            "currency":         "INR",
        },
        "premium_difference": premium_diff,
        "agent_guidance": (
            "Show the user a clear upgrade comparison:\n"
            f"  Current: {current['policy_name']} — ₹{old_final}/period\n"
            f"  New:     {target['policy_name']}  — ₹{new_final}/period  "
            f"(₹{new_loading} loading on base ₹{new_base})\n"
            f"  Difference: +₹{premium_diff}/period\n\n"
            "Ask: 'Would you like to proceed to upgrade payment?' "
            "If yes, call create_upgrade_payment with holder_id and target_policy_id."
        )
    }
