from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def escalate_claim_to_crm(claim_id: int, config: RunnableConfig) -> dict:
    """
    only call when assess_claim returned routing='escalate_crm'.
    sends high-risk claims to CRM for full investigation.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT c.claim_id, c.routing, c.claim_amount, c.assessed_amount,
                       c.claim_type, c.incident_description, c.fraud_score,
                       c.status, p.policy_name
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

    if row["routing"] != "escalate_crm":
        return {
            "status":  "wrong_routing",
            "routing": row["routing"],
            "agent_guidance": (
                f"This claim has routing='{row['routing']}', not 'escalate_crm'. "
                "Call the correct tool for this routing."
            )
        }

    if row["status"] == "escalated":
        return {
            "status":      "already_escalated",
            "claim_id":    claim_id,
            "agent_guidance": "Claim has already been escalated to CRM."
        }

    context = (
        f"CLAIM ESCALATION | Claim #{claim_id}\n"
        f"Policy: {row['policy_name']}\n"
        f"Type: {row['claim_type']}\n"
        f"Claimed Amount: ₹{row['claim_amount']}\n"
        f"Assessed Amount: ₹{row['assessed_amount']}\n"
        f"Fraud Risk Score: {row['fraud_score']}%\n"
        f"Incident: {row['incident_description']}\n"
        "Action Required: Full investigation by CRM team before any payout."
    )

    with engine.begin() as conn:
        ticket = conn.execute(
            text("""
                INSERT INTO support_tickets (user_id, reason, context, status)
                SELECT ph.user_id, 'CRM Claim Escalation', :ctx, 'open'
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                WHERE c.claim_id = :cid
                RETURNING ticket_id
            """),
            {"cid": claim_id, "ctx": context}
        ).fetchone()

        # SQLAlchemy 2.0 breaks string-key indexing on Row — use ._mapping
        ticket_id = dict(ticket._mapping)["ticket_id"]

        conn.execute(
            text("""
                UPDATE claim
                SET status = 'escalated',
                    escalation_ticket_id = :tid,
                    verdict = 'Escalated to CRM for investigation'
                WHERE claim_id = :cid
            """),
            {"tid": ticket_id, "cid": claim_id}
        )

    return {
        "status":       "escalated",
        "claim_id":     claim_id,
        "ticket_id":    ticket_id,
        "agent_guidance": (
            f"Claim #{claim_id} has been escalated to CRM (ticket #{ticket_id}). Tell the user:\n"
            "'Your claim has been flagged for a detailed review by our specialised team. "
            "This is a standard process for claims of this nature. "
            f"Your reference number is #{ticket_id}. "
            "Our team will contact you within 3-5 business days with an update. "
            "We appreciate your patience.'"
        )
    }
