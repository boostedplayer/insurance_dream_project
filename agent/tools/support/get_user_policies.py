from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def get_user_policies(config: RunnableConfig) -> dict:
    """
    Jab user apni existing/current insurance policies ke baare mein pooche tab use karo.
    Examples: 'what policies do I have?', 'show me my insurance', 'what am I covered for?',
              'list my active policies', 'what type of insurance do I hold?'

    User ke paas jo bhi policies hain unka poora detail return karta hai —
    type, description, coverage, premiums, aur validity dates sab kuch.
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
                    p.policy_description,
                    p.risk_category,
                    p.what_covers,
                    p.what_doesnt_cover,
                    p.base_premium,
                    p.coverage_amount,
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
            "status": "no_policies",
            "user_has_policy": False,
            "message": "User does not currently hold any insurance policy.",
            "agent_guidance": "Ask the user if they would like to explore new policy options."
        }

    policies = []
    for row in rows:
        row = dict(row._mapping)
        policies.append({
            "holder_id":          row["holder_id"],
            "policy_id":          row["policy_id"],
            "policy_name":        row["policy_name"],
            "policy_type":        row["policy_type"],
            "policy_description": row["policy_description"],
            "risk_category":      row["risk_category"],
            "what_covers":        row["what_covers"],
            "what_doesnt_cover":  row["what_doesnt_cover"],
            "base_premium":       row["base_premium"],
            "coverage_amount":    str(row["coverage_amount"]),
            "valid_from":         str(row["valid_from"]),
            "valid_upto":         str(row["up_to"]),
            "next_bill":          str(row["next_bill"]),
            "grace_period":       str(row["grace_period"]),
        })

    return {
        "status": "success",
        "user_has_policy": True,
        "total_policies": len(policies),
        "policies": policies,
        "agent_guidance": (
            "Present each policy clearly: name, type, what it covers, coverage amount, and validity. "
            "If the user asks deeper questions about a specific policy, use get_specific_policy_details. "
            "If they ask about billing/expiry, use gives_validity_and_next_bill_info."
        )
    }
