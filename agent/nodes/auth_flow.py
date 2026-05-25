from langchain_core.messages import SystemMessage

from agent.graph import insurance_model,insurance_prompt
from agent.state.orchestration_state import OrchestrationState

def insurance_bot(state:OrchestrationState):

    res = insurance_model.invoke([SystemMessage(content=insurance_prompt ),*state.text])
    return {"text":[res]}
 