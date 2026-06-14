from pydantic import BaseModel
from typing import Optional, Literal


class ClaimDecisionRequest(BaseModel):
    verdict: Literal["approved", "rejected"]
    approved_amount: Optional[float] = None   # required if verdict == 'approved'
    agent_notes: Optional[str] = None


class ClaimSummary(BaseModel):
    claim_id: int
    policy_name: str
    claim_type: str
    claim_amount: float
    assessed_amount: Optional[float]
    fraud_score: Optional[int]
    status: str
    routing: Optional[str]
    incident_description: Optional[str]
    filed_at: Optional[str]


class TicketSummary(BaseModel):
    ticket_id: int
    user_id: int
    reason: str
    context: Optional[str]
    status: str
    created_at: str
