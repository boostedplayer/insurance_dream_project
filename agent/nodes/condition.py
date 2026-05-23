from agent.state.model_state import ModelState

def route_by_auth(state:ModelState):
    if state.user_valid:
        return "insurance_bot"
    else:
        return "guest_flow"
