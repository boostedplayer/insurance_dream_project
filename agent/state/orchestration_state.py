from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
from uuid import uuid4

from agent.state.user import GuestResponseExtract, User
from agent.state.support_state import SupportState
from agent.state.purchase_state import PurchaseState
from agent.state.renewal_state import RenewalState
from agent.state.claim_state import ClaimState


class OrchestrationState(BaseModel):

    # Top-level conversation messages (shared across all flows)
    text: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Auth + session
    user_valid: bool = Field(default=False)
    user_info: Optional[User] = None
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    auth_user_id: Optional[int] = Field(default=None)
    prompt: str = Field(default="")

    # Guest onboarding info (collected before login)
    guest_info: GuestResponseExtract = Field(default_factory=GuestResponseExtract)
    # Kaunsa detail abhi collect ho raha hai: 'greet' → 'name' → 'email' → 'number' → 'pincode' → 'done'
    guest_stage: str = Field(default="greet")

    # Which flow is currently active — orchestrator uses this to maintain context
    # Values: 'support' | 'purchase' | 'renewal' | 'claim' | None
    current_flow: Optional[str] = Field(default=None)

    # Sub-flow states — orchestrator can read these to understand
    # what is happening inside each flow without coupling the flows together
    support_state: Optional[SupportState] = Field(default=None)
    purchase_state: Optional[PurchaseState] = Field(default=None)
    renewal_state: Optional[RenewalState] = Field(default=None)
    claim_state: Optional[ClaimState] = Field(default=None)
