from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def gives_validity_and_next_bill_info(config: RunnableConfig) -> dict:
    """
    use when user asks about policy validity, expiry, next billing date, or grace period.
    returns valid_from, valid_upto, next_bill, and grace_period for all held policies.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    ph.holder_id,
                    ph.policy_id,
                    p.policy_name,
                    p.policy_type,
                    ph.valid_from,
                    ph.next_bill,
                    ph.up_to,
                    ph.grace_period
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.user_id = :user_id
            """),
            {"user_id": auth_user_id}
        ).fetchall()

    if not rows:
        return {
            "status": "no_policy_found",
            "user_has_policy": False,
            "message": "User does not currently hold any insurance policy."
        }

    policies = []
    for row in rows:
        row = dict(row._mapping)
        policies.append({
            "holder_id":        row["holder_id"],
            "policy_id":        row["policy_id"],
            "policy_name":      row["policy_name"],
            "policy_type":      row["policy_type"],
            "valid_from":       str(row["valid_from"]),
            "next_bill":        str(row["next_bill"]),
            "valid_upto":       str(row["up_to"]),
            "grace_period_days": str(row["grace_period"]),
        })

    return {
        "status": "success",
        "user_has_policy": True,
        "total_policies": len(policies),
        "policies": policies,
    }
