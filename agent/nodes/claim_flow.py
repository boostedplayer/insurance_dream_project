from langchain_core.messages import SystemMessage

from agent.state.orchestration_state import OrchestrationState
from agent.prompts.claim_prompt import claim_prompt


async def claim_bot(state: OrchestrationState):
    from agent.graph import claim_model

    res = await claim_model.ainvoke([SystemMessage(content=claim_prompt), *state.text])

    return {
        "text":         [res],
        "current_flow": "claim",
    }
