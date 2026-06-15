from langgraph.graph import END
from langchain_core.messages import AIMessage

from agent.state.orchestration_state import OrchestrationState


_PURCHASE_TOOL_NAMES = {
    "initiate_purchase",
    "create_payment_order",
    "confirm_purchase",
}

_RENEWAL_TOOL_NAMES = {
    "get_renewal_summary",
    "create_renewal_payment",
    "confirm_renewal",
    "get_upgrade_options",
    "initiate_upgrade",
    "create_upgrade_payment",
    "confirm_upgrade",
    "cancel_policy",
}

_CLAIM_TOOL_NAMES = {
    "initiate_claim",
    "assess_claim",
    "approve_claim",
    "flag_for_human_review",
    "escalate_claim_to_crm",
    "check_claim_status",
}


def route_by_auth(state: OrchestrationState):
    # authenticated → orchestrator, otherwise guest onboarding
    if state.user_valid:
        return "orchestrator"
    else:
        return "guest_flow"


def route_from_orchestrator(state: OrchestrationState):
    """routes to the right flow bot based on current_flow; general chat already handled → END."""
    mapping = {
        "support":  "support_bot",
        "purchase": "purchase_bot",
        "renewal":  "renewal_bot",
        "claim":    "claim_bot",
    }
    return mapping.get(state.current_flow, END)


def route_after_support_bot(state: OrchestrationState):
    """tool call → support tools, otherwise done."""
    last_msg = state.text[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return END
    return "tools"


def route_after_purchase_bot(state: OrchestrationState):
    last_msg = state.text[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return END
    return "purchase_tools"


def route_after_renewal_bot(state: OrchestrationState):
    last_msg = state.text[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return END
    return "renewal_tools"


def route_after_claim_bot(state: OrchestrationState):
    last_msg = state.text[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return END
    return "claim_tools"
