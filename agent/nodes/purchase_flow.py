from langchain_core.messages import SystemMessage

from agent.state.orchestration_state import OrchestrationState
from agent.prompts.purchase_prompt import purchase_prompt


async def purchase_bot(state: OrchestrationState):
    from agent.graph import purchase_model

    res = await purchase_model.ainvoke([SystemMessage(content=purchase_prompt), *state.text])

    return {
        "text":         [res],
        "current_flow": "purchase",
    }
