from agent.state.orchestration_state import OrchestrationState

def route_by_auth(state:OrchestrationState):
    if state.user_valid:
        return "insurance_bot"
    else:
        return "guest_flow"
