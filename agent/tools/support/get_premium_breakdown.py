from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def get_premium_breakdown(config: RunnableConfig) -> dict:
    """
    use when user asks why their premium is high or how it was calculated.
    returns latest underwriting result with base premium, risk loading, and final premium per policy.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    # grab most recent risk assessment
    with engine.connect() as conn:
        underwriting = conn.execute(
            text("""
                SELECT risk_score, risk_category, loading_percent, created_at
                FROM underwriting_results
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"user_id": auth_user_id}
        ).fetchone()

    if underwriting is None:
        return {
            "status": "no_underwriting_found",
            "message": "No risk assessment found for this user.",
            "agent_guidance": (
                "Tell the user their premium hasn't been calculated yet. "
                "Ask if they'd like to explore a new policy — that will trigger the assessment."
            )
        }

    uw = dict(underwriting._mapping)

    # fetch held policies so we can break down premium per policy
    with engine.connect() as conn:
        policies = conn.execute(
            text("""
                SELECT p.policy_name, p.policy_type, p.base_premium, p.coverage_amount
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.user_id = :user_id
            """),
            {"user_id": auth_user_id}
        ).fetchall()

    loading_pct = float(uw["loading_percent"])

    policy_breakdowns = []
    for p in policies:
        p = dict(p._mapping)
        base = float(p["base_premium"] or 0)
        loading_amount = round(base * loading_pct, 2)
        final_premium  = round(base + loading_amount, 2)
        policy_breakdowns.append({
            "policy_name":         p["policy_name"],
            "policy_type":         p["policy_type"],
            "coverage_amount":     str(p["coverage_amount"]),
            "base_premium":        base,
            "risk_loading_percent": round(loading_pct * 100, 1),
            "loading_amount":      loading_amount,
            "final_premium":       final_premium,
        })

    return {
        "status": "success",
        "risk_assessment": {
            "risk_score":     round(float(uw["risk_score"]), 2),
            "risk_category":  uw["risk_category"],
            "assessed_on":    str(uw["created_at"]),
        },
        "premium_breakdowns": policy_breakdowns,
        "agent_guidance": (
            "Explain the premium using the risk_assessment block first — tell the user their "
            "risk score and category in plain English. Then walk through each policy's breakdown: "
            "base premium + loading amount = final premium. "
            "Explain that the loading percentage reflects their risk profile. "
            "Do not suggest the score can be changed — it's based on their profile data."
        )
    }
