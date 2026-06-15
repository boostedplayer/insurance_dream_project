from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def get_claim_history(config: RunnableConfig) -> dict:
    """
    use when user asks about their past or current claims.
    returns all filed claims with type, amount, status, and verdict.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    c.claim_id,
                    c.claim_type,
                    c.claim_amount,
                    c.status,
                    c.verdict,
                    c.fraud_score,
                    p.policy_name,
                    p.policy_type
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                JOIN policy p        ON ph.policy_id = p.policy_id
                WHERE ph.user_id = :user_id
                ORDER BY c.claim_id DESC
            """),
            {"user_id": auth_user_id}
        ).fetchall()

    if not rows:
        return {
            "status": "no_claims",
            "has_claims": False,
            "message": "No claims found for this user.",
            "agent_guidance": "Inform the user they have no claim history on record."
        }

    claims = []
    for row in rows:
        row = dict(row._mapping)
        claims.append({
            "claim_id":     row["claim_id"],
            "policy_name":  row["policy_name"],
            "policy_type":  row["policy_type"],
            "claim_type":   row["claim_type"],
            "claim_amount": str(row["claim_amount"]),
            "status":       row["status"],
            "verdict":      row["verdict"],
        })

    return {
        "status": "success",
        "has_claims": True,
        "total_claims": len(claims),
        "claims": claims,
        "agent_guidance": (
            "Present each claim clearly: policy it was filed under, claim type, amount, "
            "and current status/verdict. If the user asks to raise a new claim, "
            "that is handled by the claims flow — not this tool."
        )
    }
