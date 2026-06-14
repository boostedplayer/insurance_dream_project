from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def flag_for_human_review(claim_id: int, config: RunnableConfig) -> dict:
    """
    Tab use karo jab assess_claim ne routing='human_review' return kiya ho.
    Claim ko manual review ke liye flag karta hai — ek human agent pehle dekhega, phir approval ya rejection hogi.
    Human agent claim ki details review karke decision submit karega.

    claim_id — woh claim ID jo initiate_claim / assess_claim se mili hai.
    Returns: confirmation ki claim human review queue mein aa gaya hai.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT c.claim_id, c.routing, c.claim_amount, c.assessed_amount,
                       c.status, c.claim_type, p.policy_name
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

    if row["routing"] != "human_review":
        return {
            "status":  "wrong_routing",
            "routing": row["routing"],
            "agent_guidance": (
                f"This claim has routing='{row['routing']}', not 'human_review'. "
                "Call the correct tool for this routing."
            )
        }

    if row["status"] == "human_review":
        return {
            "status":      "already_queued",
            "claim_id":    claim_id,
            "agent_guidance": "Claim is already in the human review queue."
        }

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE claim SET status = 'human_review' WHERE claim_id = :cid"),
            {"cid": claim_id}
        )
        # Human team ko dikhne ke liye support_tickets mein bhi log kar do
        conn.execute(
            text("""
                INSERT INTO support_tickets (user_id, reason, context, status)
                SELECT ph.user_id,
                       'Claim human review required',
                       :ctx,
                       'open'
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                WHERE c.claim_id = :cid
            """),
            {
                "cid": claim_id,
                "ctx": (
                    f"Claim #{claim_id} | Type: {row['claim_type']} | "
                    f"Policy: {row['policy_name']} | "
                    f"Claimed: ₹{row['claim_amount']} | Assessed: ₹{row['assessed_amount']} | "
                    "Requires human agent decision before payout."
                )
            }
        )

    return {
        "status":   "queued_for_review",
        "claim_id": claim_id,
        "agent_guidance": (
            f"Claim #{claim_id} has been sent to a human agent for review. Tell the user:\n"
            "'Your claim requires a quick manual review by our team before we can process it. "
            "This usually takes 1-2 business days. "
            "You will be notified on your registered email once a decision is made. "
            "You can also check the status anytime by asking me about your claim.'"
        )
    }
