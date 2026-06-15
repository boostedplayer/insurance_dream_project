from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def initiate_purchase(policy_name: str, config: RunnableConfig) -> dict:
    """
    call before create_payment_order — fetches the user's personalized premium and shows a purchase summary.
    use when user has decided which policy they want ('I want to buy SecureHealth Plus', etc.).
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        # must fetch risk_category first — each policy_name has 7 variants (one per risk tier).
        # name-only LIKE match was picking the cheapest variant, halving the premium/coverage shown.
        # support flow already filtered by risk_category, so it was fine; purchase flow wasn't.
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
            # no risk category — can show a matching policy but can't commit a premium yet
            policy = conn.execute(
                text("""
                    SELECT policy_id, policy_name, policy_type,
                           base_premium, coverage_amount
                    FROM policy
                    WHERE LOWER(policy_name) LIKE LOWER(:name)
                    ORDER BY policy_id LIMIT 1
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

            policy = dict(policy._mapping)
            return {
                "status": "no_underwriting",
                "policy": {
                    "policy_id":      policy["policy_id"],
                    "policy_name":    policy["policy_name"],
                    "policy_type":    policy["policy_type"],
                },
                "agent_guidance": (
                    "User has not been risk-assessed yet, so their personalized premium and the "
                    "correct policy variant cannot be determined. Tell them a quick risk assessment "
                    "is needed first — ask them to describe their insurance needs so you can run "
                    "new_policy_inquiry, then retry the purchase."
                )
            }

        uw = dict(underwriting._mapping)
        risk_category = uw["risk_category"]

        # match on name + risk_category to get the exact variant the support flow showed
        policy = conn.execute(
            text("""
                SELECT policy_id, policy_name, policy_type, policy_description,
                       base_premium, coverage_amount, policy_tenure,
                       what_covers, what_doesnt_cover
                FROM policy
                WHERE LOWER(policy_name) LIKE LOWER(:name)
                  AND risk_category = :risk_category
                ORDER BY policy_id LIMIT 1
            """),
            {"name": f"%{policy_name}%", "risk_category": risk_category}
        ).fetchone()

        # defensive fallback: no variant for this risk_category, try name-only match
        if not policy:
            policy = conn.execute(
                text("""
                    SELECT policy_id, policy_name, policy_type, policy_description,
                           base_premium, coverage_amount, policy_tenure,
                           what_covers, what_doesnt_cover
                    FROM policy
                    WHERE LOWER(policy_name) LIKE LOWER(:name)
                    ORDER BY policy_id LIMIT 1
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

        policy    = dict(policy._mapping)
        policy_id = policy["policy_id"]

    base_premium   = float(policy["base_premium"])
    loading_pct    = float(uw["loading_percent"])
    loading_amount = round(base_premium * loading_pct, 2)
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
            f"  Risk loading:    {round(loading_pct * 100, 1)}% = ₹{loading_amount}  (your risk category: {uw['risk_category']})\n"
            f"  Final premium:   ₹{final_premium} per period\n\n"
            "Then ask: 'Would you like to proceed to payment?' "
            "If yes, call create_payment_order with policy_id."
        )
    }
