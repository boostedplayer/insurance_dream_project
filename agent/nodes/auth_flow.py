from langchain_core.messages import SystemMessage

from agent.prompts.insurance_prompt import insurance_prompt
from agent.state.orchestration_state import OrchestrationState


async def support_bot(state: OrchestrationState):
    """
    Support flow ka bot — sirf support tools use karta hai (FAQ, policy details, compare,
    new policy inquiry, claim history, escalate, etc.). Orchestrator isi par route karti hai
    jab user ki intent support/explore/Q&A hoti hai.
    """
    from agent.graph import support_model

    res = await support_model.ainvoke([SystemMessage(content=insurance_prompt), *state.text])
    return {"text": [res], "current_flow": "support"}
