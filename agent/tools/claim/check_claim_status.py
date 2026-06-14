from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
from typing import Optional


@tool
def check_claim_status(config: RunnableConfig, claim_id: Optional[int] = None) -> dict:
    """
    Jab user apne claim ka update maange tab use karo.
    Examples: 'what happened to my claim?', 'is my claim approved?',
              'what is the status of claim #5?', 'any update on my claim?'

    claim_id — optional hai. Agar nahi diya, toh user ka sabse latest claim laata hai.
    Returns: claim ka current status, routing, verdict, aur approved amount agar applicable ho.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        if claim_id:
            row = conn.execute(
                text("""
                    SELECT c.claim_id, c.claim_type, c.claim_amount, c.assessed_amount,
                           c.approved_amount, c.fraud_score, c.status, c.verdict,
                           c.routing, c.escalation_ticket_id, c.incident_description,
                           c.created_at, p.policy_name
                    FROM claim c
                    JOIN policyholder ph ON c.holder_id = ph.holder_id
                    JOIN policy p        ON ph.policy_id = p.policy_id
                    WHERE c.claim_id = :cid AND ph.user_id = :uid
                """),
                {"cid": claim_id, "uid": auth_user_id}
            ).fetchone()
        else:
            row = conn.execute(
                text("""
                    SELECT c.claim_id, c.claim_type, c.claim_amount, c.assessed_amount,
                           c.approved_amount, c.fraud_score, c.status, c.verdict,
                           c.routing, c.escalation_ticket_id, c.incident_description,
                           c.created_at, p.policy_name
                    FROM claim c
                    JOIN policyholder ph ON c.holder_id = ph.holder_id
                    JOIN policy p        ON ph.policy_id = p.policy_id
                    WHERE ph.user_id = :uid
                    ORDER BY c.claim_id DESC LIMIT 1
                """),
                {"uid": auth_user_id}
            ).fetchone()

    if not row:
        return {
            "status": "no_claims",
            "agent_guidance": "No claims found for this user. Ask if they'd like to file a new claim."
        }

    row = dict(row._mapping)

    status_messages = {
        "initiated":    "Your claim has been received and is being processed.",
        "under_review": "Your claim is currently under assessment.",
        "human_review": "Your claim is pending review by a human agent (1-2 business days).",
        "escalated":    f"Your claim has been escalated to our specialised team (ref: #{row['escalation_ticket_id']}). Expected timeline: 3-5 business days.",
        "approved":     f"Your claim has been APPROVED. ₹{row['approved_amount']} will be disbursed within 5-7 working days.",
        "rejected":     f"Your claim was not approved. Reason: {row['verdict']}",
    }

    user_message = status_messages.get(row["status"], f"Status: {row['status']}")

    return {
        "claim_id":         row["claim_id"],
        "policy_name":      row["policy_name"],
        "claim_type":       row["claim_type"],
        "claimed_amount":   str(row["claim_amount"]),
        "assessed_amount":  str(row["assessed_amount"]) if row["assessed_amount"] else None,
        "approved_amount":  str(row["approved_amount"]) if row["approved_amount"] else None,
        "status":           row["status"],
        "verdict":          row["verdict"],
        "routing":          row["routing"],
        "filed_at":         str(row["created_at"]) if row["created_at"] else None,
        "agent_guidance": (
            f"Tell the user: '{user_message}' "
            "If they have questions about why a claim was rejected or escalated, "
            "offer to escalate_to_support to connect them with a human agent."
        )
    }
