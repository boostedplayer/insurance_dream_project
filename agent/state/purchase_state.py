from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated


class PurchaseState(BaseModel):
    """
    State for the Purchase flow.
    Tracks which policy the user is buying, the premium calculated for them,
    the Razorpay payment link, and the final activation result.

    Flow:  initiate_purchase → create_payment_order → [user pays] → confirm_purchase
    """

    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Policy the user wants to buy (set by initiate_purchase)
    selected_policy_id: Optional[int] = Field(default=None)
    selected_policy_name: Optional[str] = Field(default=None)
    selected_policy_type: Optional[str] = Field(default=None)

    # Risk-adjusted pricing (set by initiate_purchase)
    base_premium: Optional[float] = Field(default=None)
    risk_category: Optional[str] = Field(default=None)
    loading_percent: Optional[float] = Field(default=None)
    loading_amount: Optional[float] = Field(default=None)
    final_premium: Optional[float] = Field(default=None)

    # Razorpay payment info (set by create_payment_order)
    payment_link_id: Optional[str] = Field(default=None)   # Razorpay payment link ID
    payment_url: Optional[str] = Field(default=None)       # Short URL shared with user

    # Status of the purchase
    # Possible values: 'browsing' → 'summary_shown' → 'payment_initiated' → 'completed' | 'failed'
    purchase_status: Optional[str] = Field(default=None)

    # Set after confirm_purchase succeeds
    order_id: Optional[int] = Field(default=None)          # purchase_orders.order_id
    holder_id: Optional[int] = Field(default=None)         # policyholder.holder_id
    policy_valid_from: Optional[str] = Field(default=None)
    policy_up_to: Optional[str] = Field(default=None)
    next_bill_date: Optional[str] = Field(default=None)
