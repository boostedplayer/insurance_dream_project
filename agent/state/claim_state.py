from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated, Literal


class ClaimState(BaseModel):
    """
    State for the Claims flow.

    Full lifecycle:
      User describes incident
        → eligibility check (is the policy active? does it cover this?)
        → fraud + amount assessment (ML score)
        → auto-approve (low risk) OR human-in-loop (borderline) OR CRM escalation (high risk / complex)
        → final verdict stored in DB
    """

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Which policy this claim is filed under
    holder_id: Optional[int] = Field(default=None)
    policy_id: Optional[int] = Field(default=None)
    policy_name: Optional[str] = Field(default=None)

    # Claim details provided by user
    claim_type: Optional[str] = Field(default=None)
    # e.g. 'medical_expense', 'hospitalization', 'accident', 'theft', 'third_party_damage'
    incident_description: Optional[str] = Field(default=None)
    claimed_amount: Optional[float] = Field(default=None)

    # Eligibility result (does this policy cover this claim type?)
    is_eligible: Optional[bool] = Field(default=None)
    ineligibility_reason: Optional[str] = Field(default=None)

    # ML / rule-based assessment
    fraud_score: Optional[float] = Field(default=None)          # 0.0 – 1.0
    assessed_amount: Optional[float] = Field(default=None)      # amount agent recommends approving
    assessment_notes: Optional[str] = Field(default=None)

    # Routing decision after assessment
    # 'auto_approve' → no human needed
    # 'human_review'  → borderline case, human must confirm before finalisation
    # 'escalate_crm'  → complex / high fraud risk, sent to CRM agent
    routing: Optional[Literal["auto_approve", "human_review", "escalate_crm"]] = Field(default=None)

    # Human-in-the-loop fields (filled when routing == 'human_review')
    requires_human_approval: bool = Field(default=False)
    human_decision: Optional[Literal["approved", "rejected"]] = Field(default=None)
    human_agent_notes: Optional[str] = Field(default=None)

    # CRM escalation (filled when routing == 'escalate_crm')
    escalation_ticket_id: Optional[int] = Field(default=None)

    # Final outcome stored in DB
    claim_id: Optional[int] = Field(default=None)
    # 'initiated' → 'under_review' → 'approved' | 'rejected' | 'escalated'
    claim_status: Optional[str] = Field(default=None)
    final_verdict: Optional[str] = Field(default=None)
    approved_amount: Optional[float] = Field(default=None)
