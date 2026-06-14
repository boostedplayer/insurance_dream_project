from fastapi import APIRouter, HTTPException, Depends
from agent.db.db import engine
from sqlalchemy import text
from api.schemas.admin import ClaimDecisionRequest, ClaimSummary, TicketSummary
from api.dependencies import get_current_user
from typing import List

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/claims/pending", response_model=List[ClaimSummary])
def list_pending_claims(user: dict = Depends(get_current_user)):
    """
    Jo claims human review ka intezaar kar rahe hain, unhe saare laao.
    Django admin panel mein human agent queue dikhane ke liye use hota hai.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT c.claim_id, p.policy_name, c.claim_type, c.claim_amount,
                       c.assessed_amount, c.fraud_score, c.status, c.routing,
                       c.incident_description, c.created_at
                FROM claim c
                JOIN policyholder ph ON c.holder_id = ph.holder_id
                JOIN policy p        ON ph.policy_id = p.policy_id
                WHERE c.status = 'human_review'
                ORDER BY c.created_at ASC
            """)
        ).fetchall()

    return [
        ClaimSummary(
            claim_id=r["claim_id"],
            policy_name=r["policy_name"],
            claim_type=r["claim_type"],
            claim_amount=float(r["claim_amount"]),
            assessed_amount=float(r["assessed_amount"]) if r["assessed_amount"] else None,
            fraud_score=r["fraud_score"],
            status=r["status"],
            routing=r["routing"],
            incident_description=r["incident_description"],
            filed_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in rows
    ]


@router.post("/claims/{claim_id}/decision")
def submit_claim_decision(
    claim_id: int,
    body: ClaimDecisionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Human agent apna decision claim pe submit karta hai jo human review mein pada hai.
    Django admin panel se call hota hai jab agent claim ki details review kar leta hai.
    """
    with engine.connect() as conn:
        claim = conn.execute(
            text("SELECT claim_id, status FROM claim WHERE claim_id = :cid"),
            {"cid": claim_id}
        ).fetchone()

    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if dict(claim._mapping)["status"] != "human_review":
        raise HTTPException(status_code=400, detail="Claim is not in human_review status")

    if body.verdict == "approved" and not body.approved_amount:
        raise HTTPException(status_code=422, detail="approved_amount is required when approving a claim")

    new_status = "approved" if body.verdict == "approved" else "rejected"
    verdict_text = (
        f"Approved by human agent. Payout: ₹{body.approved_amount}"
        if body.verdict == "approved"
        else "Rejected by human agent."
    )

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE claim
                SET status          = :status,
                    verdict         = :verdict,
                    approved_amount = :amount,
                    human_agent_notes = :notes
                WHERE claim_id = :cid
            """),
            {
                "status":  new_status,
                "verdict": verdict_text,
                "amount":  body.approved_amount,
                "notes":   body.agent_notes,
                "cid":     claim_id,
            }
        )

        if body.verdict == "approved":
            conn.execute(
                text("""
                    UPDATE users u
                    SET claims_history = COALESCE(claims_history, 0) + 1
                    FROM policyholder ph
                    WHERE ph.holder_id = (SELECT holder_id FROM claim WHERE claim_id = :cid)
                    AND ph.user_id = u.user_id
                """),
                {"cid": claim_id}
            )

    return {
        "claim_id": claim_id,
        "verdict":  body.verdict,
        "message":  f"Claim #{claim_id} has been {body.verdict}."
    }


@router.get("/tickets", response_model=List[TicketSummary])
def list_open_tickets(user: dict = Depends(get_current_user)):
    """
    Saare open support tickets aur CRM escalations laao.
    Django admin aur CRM panel ke liye use hota hai.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT ticket_id, user_id, reason, context, status, created_at
                FROM support_tickets
                WHERE status = 'open'
                ORDER BY created_at ASC
            """)
        ).fetchall()

    return [
        TicketSummary(
            ticket_id=r["ticket_id"],
            user_id=r["user_id"],
            reason=r["reason"],
            context=r["context"],
            status=r["status"],
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    """Support ticket ko resolved mark kar do."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE support_tickets SET status = 'closed' WHERE ticket_id = :tid"),
            {"tid": ticket_id}
        )
    return {"ticket_id": ticket_id, "status": "closed"}
