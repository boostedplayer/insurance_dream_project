from langchain_core.messages import SystemMessage

from agent.state.orchestration_state import OrchestrationState
from agent.prompts.renewal_prompt import renewal_prompt


async def renewal_bot(state: OrchestrationState):
    from agent.graph import renewal_model

    res = await renewal_model.ainvoke([SystemMessage(content=renewal_prompt), *state.text])

    return {
        "text":         [res],
        "current_flow": "renewal",
    }
