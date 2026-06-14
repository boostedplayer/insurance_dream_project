from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated


class SupportState(BaseModel):
    """
    State for the Support flow.
    Tracks the conversation, what the user is currently asking about,
    and any support ticket raised during the session.
    """

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # What topic the user is currently on — helps the LLM stay on context
    # e.g. 'faq', 'policy_details', 'premium_breakdown', 'claim_history', 'escalation'
    current_topic: Optional[str] = Field(default=None)

    # Populated when escalate_to_support is called
    ticket_id: Optional[int] = Field(default=None)
    ticket_status: Optional[str] = Field(default=None)  # 'open' | 'resolved'
