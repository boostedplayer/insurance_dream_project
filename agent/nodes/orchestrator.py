from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agent.state.orchestration_state import OrchestrationState
from agent.prompts.orchestrator_prompt import orchestrator_prompt, general_prompt


def _as_text(content) -> str:
    """normalize to str — gemini returns list-of-blocks, others return str."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
            else (b if isinstance(b, str) else "")
            for b in content
        )
    return str(content) if content else ""


def _clean_history(messages):
    """strip tool calls and ToolMessages — router/general model has no tools bound, confuses gemini."""
    cleaned = []
    for m in messages:
        if isinstance(m, HumanMessage):
            cleaned.append(m)
        elif isinstance(m, AIMessage) and not m.tool_calls:
            txt = _as_text(m.content)
            if txt.strip():
                cleaned.append(AIMessage(content=txt))
    return cleaned


async def orchestrator(state: OrchestrationState):
    """runs every turn, picks which flow to route to (or handles general chat directly)."""
    from agent.graph import router_model, general_model

    history = _clean_history(state.text)

    decision = await router_model.ainvoke([
        SystemMessage(content=orchestrator_prompt.format(current_flow=state.current_flow or "none")),
        *history,
    ])

    flow = decision.flow

    # general chat — reply directly, don't route to any flow
    if flow == "general":
        reply = await general_model.ainvoke([
            SystemMessage(content=general_prompt),
            *history,
        ])
        return {"text": [reply], "current_flow": None}

    # just set current_flow — the conditional edge handles the actual routing
    return {"current_flow": flow}
