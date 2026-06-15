from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def approve_claim(claim_id: int, config: RunnableConfig) -> dict:
    """
    only call this when assess_claim returned routing='auto_approve'.
    don't call for human_review or escalate_crm routings.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT c.claim_id, c.routing, c.assessed_amount, c.status,
                       p.policy_name
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                JOIN policy p        ON ph.policy_id = p.policy_id
                WHERE c.claim_id = :cid AND ph.user_id = :uid
            """),
            {"cid": claim_id, "uid": auth_user_id}
        ).fetchone()

    if not row:
        return {"status": "not_found", "agent_guidance": "Claim not found."}

    row = dict(row._mapping)

    if row["routing"] != "auto_approve":
        return {
            "status": "wrong_routing",
            "routing": row["routing"],
            "agent_guidance": (
                f"This claim has routing='{row['routing']}', not 'auto_approve'. "
                "Call the correct tool for this routing."
            )
        }

    if row["status"] == "approved":
        return {
            "status":          "already_approved",
            "approved_amount": str(row["assessed_amount"]),
            "agent_guidance":  "This claim was already approved."
        }

    approved_amount = float(row["assessed_amount"])

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE claim
                SET status = 'approved',
                    approved_amount = :amt,
                    verdict = 'Auto-approved after risk assessment'
                WHERE claim_id = :cid
            """),
            {"amt": approved_amount, "cid": claim_id}
        )
        # bump claims_history counter
        conn.execute(
            text("""
                UPDATE users u
                SET claims_history = COALESCE(claims_history, 0) + 1
                FROM policyholder ph
                WHERE ph.holder_id = (
                    SELECT holder_id FROM claim WHERE claim_id = :cid
                )
                AND ph.user_id = u.user_id
            """),
            {"cid": claim_id}
        )

    return {
        "status":          "approved",
        "claim_id":        claim_id,
        "policy_name":     row["policy_name"],
        "approved_amount": approved_amount,
        "currency":        "INR",
        "agent_guidance": (
            f"Claim #{claim_id} approved! Tell the user:\n"
            f"'Great news! Your claim has been approved. "
            f"₹{approved_amount} will be disbursed to your registered bank account within 5-7 working days. "
            "You will receive a confirmation on your registered email.'"
        )
    }
