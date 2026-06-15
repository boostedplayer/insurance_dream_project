from langchain_core.messages import SystemMessage

from agent.prompts.insurance_prompt import insurance_prompt
from agent.state.orchestration_state import OrchestrationState


async def support_bot(state: OrchestrationState):
    """handles support intents — faq, policy details, compare, claim history, escalate, etc."""
    from agent.graph import support_model

    res = await support_model.ainvoke([SystemMessage(content=insurance_prompt), *state.text])
    return {"text": [res], "current_flow": "support"}
