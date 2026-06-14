from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
from datetime import date


def _compute_fraud_score(claimed_amount: float, coverage_amount: float,
                         claims_history: int, days_since_start: int) -> float:
    score = 0.0

    # Claim aur coverage ka ratio dekho — kitna risk hai
    ratio = claimed_amount / coverage_amount if coverage_amount else 1.0
    if ratio > 0.90:
        score += 0.35
    elif ratio > 0.60:
        score += 0.20
    elif ratio > 0.30:
        score += 0.10

    # Baar baar claim karne wale ka risk check karo
    if claims_history >= 5:
        score += 0.35
    elif claims_history >= 3:
        score += 0.20
    elif claims_history >= 1:
        score += 0.10

    # Naya policy leke turant claim karna — yeh suspicious lagta hai
    if days_since_start < 30:
        score += 0.30
    elif days_since_start < 90:
        score += 0.15

    return min(round(score, 2), 1.0)


@tool
def assess_claim(claim_id: int, config: RunnableConfig) -> dict:
    """
    initiate_claim ke turant baad use karo. Claim ki eligibility check aur fraud/risk assessment karta hai,
    phir ek routing decision return karta hai jis par bot ko act karna chahiye.

    claim_id — woh ID jo initiate_claim ne return ki thi.

    Routing decisions:
      'auto_approve'  → aage approve_claim call karo
      'human_review'  → aage flag_for_human_review call karo
      'escalate_crm'  → aage escalate_claim_to_crm call karo
      'rejected'      → claim eligible nahi hai, user ko batao

    Returns: fraud_score, assessed_amount, routing, aur next step ke liye agent_guidance.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT
                    c.claim_id, c.claim_type, c.claim_amount, c.incident_description, c.status,
                    ph.valid_from,
                    p.coverage_amount, p.what_covers, p.what_doesnt_cover,
                    u.claims_history
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                JOIN policy p        ON ph.policy_id = p.policy_id
                JOIN users u         ON ph.user_id   = u.user_id
                WHERE c.claim_id = :cid AND u.user_id = :uid
            """),
            {"cid": claim_id, "uid": auth_user_id}
        ).fetchone()

    if not row:
        return {
            "status": "not_found",
            "agent_guidance": "Claim not found. Verify the claim_id."
        }

    row = dict(row._mapping)

    # ── Eligibility check — dekho claim cover hota hai ya nahi ───────────────
    claim_type_lower    = row["claim_type"].lower()
    what_doesnt_cover   = (row["what_doesnt_cover"] or "").lower()

    # Simple keyword match — agar claim type exclusion mein hai toh reject karo
    is_ineligible = any(
        keyword in what_doesnt_cover
        for keyword in [claim_type_lower, claim_type_lower.replace("_", " ")]
    )

    if is_ineligible:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE claim SET status = 'rejected',
                        verdict = 'Claim type not covered under this policy',
                        routing = 'rejected'
                    WHERE claim_id = :cid
                """),
                {"cid": claim_id}
            )
        return {
            "status":  "rejected",
            "claim_id": claim_id,
            "reason":  f"'{row['claim_type']}' is listed under policy exclusions.",
            "agent_guidance": (
                "Inform the user their claim has been rejected because this claim type "
                "is not covered under their policy. Show them what IS covered and suggest "
                "they call escalate_to_support if they believe this is an error."
            )
        }

    # ── Fraud / risk scoring — kitna risky hai yeh claim ─────────────────────
    today            = date.today()
    valid_from       = row["valid_from"]
    days_since_start = (today - valid_from).days if hasattr(valid_from, '__rsub__') else 180

    claimed_amount   = float(row["claim_amount"])
    coverage_amount  = float(row["coverage_amount"])
    claims_history   = int(row["claims_history"] or 0)

    fraud_score      = _compute_fraud_score(claimed_amount, coverage_amount, claims_history, days_since_start)
    fraud_score_int  = int(fraud_score * 100)   # 0-100 integer mein store karo

    # Assessed payout — 10% deductible kaato, aur coverage se zyada nahi
    assessed_amount  = round(min(claimed_amount, coverage_amount) * 0.90, 2)

    # ── Routing decision — claim kahan bhejein ────────────────────────────────
    if fraud_score < 0.35:
        routing = "auto_approve"
    elif fraud_score < 0.65:
        routing = "human_review"
    else:
        routing = "escalate_crm"

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE claim
                SET fraud_score     = :fs,
                    assessed_amount = :aa,
                    routing         = :rt,
                    status          = 'under_review'
                WHERE claim_id = :cid
            """),
            {"fs": fraud_score_int, "aa": assessed_amount, "rt": routing, "cid": claim_id}
        )

    next_step = {
        "auto_approve":  "Call approve_claim with this claim_id.",
        "human_review":  "Call flag_for_human_review with this claim_id.",
        "escalate_crm":  "Call escalate_claim_to_crm with this claim_id.",
    }[routing]

    return {
        "status":           "assessed",
        "claim_id":         claim_id,
        "fraud_score":      fraud_score,
        "fraud_score_pct":  fraud_score_int,
        "assessed_amount":  assessed_amount,
        "routing":          routing,
        "agent_guidance": (
            f"Assessment complete. Fraud score: {fraud_score_int}%. Routing: {routing}. "
            f"Assessed payout: ₹{assessed_amount}. Next step: {next_step}"
        )
    }
