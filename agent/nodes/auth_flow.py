from langchain_core.messages import SystemMessage

from agent.graph import insurance_model,insurance_prompt
from agent.state.model_state import ModelState

def insurance_bot(state:ModelState):

    res = insurance_model.invoke([SystemMessage(content=insurance_prompt ),*state.text])
    return {"text":[res]}
 