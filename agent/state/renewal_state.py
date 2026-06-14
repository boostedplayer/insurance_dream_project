from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated, Literal


class RenewalState(BaseModel):
    """
    State for the Policy Management flow (renew / upgrade / cancel).
    Covers all three actions a user can take on an existing policy.

    Renew:   same policy, extend validity, payment required
    Upgrade: move to a higher-tier policy, premium difference charged
    Cancel:  exit current policy, no payment needed
    """

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Which policyholder record the user is acting on
    selected_holder_id: Optional[int] = Field(default=None)
    selected_policy_id: Optional[int] = Field(default=None)
    selected_policy_name: Optional[str] = Field(default=None)
    current_policy_up_to: Optional[str] = Field(default=None)   # expiry date of current policy

    # Action the user wants to perform
    action: Optional[Literal["renew", "upgrade", "cancel"]] = Field(default=None)

    # --- Upgrade specific ---
    target_policy_id: Optional[int] = Field(default=None)       # new policy to upgrade to
    target_policy_name: Optional[str] = Field(default=None)
    upgrade_premium_diff: Optional[float] = Field(default=None) # extra amount to pay

    # --- Renew / Upgrade payment ---
    renewal_payment_link_id: Optional[str] = Field(default=None)
    renewal_payment_url: Optional[str] = Field(default=None)
    renewal_amount: Optional[float] = Field(default=None)

    # Overall status of this policy management session
    # 'idle' → 'action_selected' → 'summary_shown' → 'payment_initiated' → 'completed' | 'cancelled'
    management_status: Optional[str] = Field(default=None)

    # New policy dates after renew / upgrade completes
    new_valid_from: Optional[str] = Field(default=None)
    new_up_to: Optional[str] = Field(default=None)
    new_next_bill: Optional[str] = Field(default=None)
