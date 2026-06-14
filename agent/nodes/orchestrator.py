from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agent.state.orchestration_state import OrchestrationState
from agent.prompts.orchestrator_prompt import orchestrator_prompt, general_prompt


def _as_text(content) -> str:
    """Message content ko plain string banao — Gemini list-of-blocks deta hai, baaki string."""
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
    """
    Sirf saaf conversational turns rakho — tool calls aur ToolMessages hata do.
    Router aur general model ke paas koi tools bind nahi hain, isliye unhe
    tool-laden history dena Gemini ko confuse kar sakta hai.
    """
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
    """
    Routing brain — har turn pe chalti hai. User ke latest message ko padh ke decide karti hai
    ki kaunsi flow handle karegi (support / purchase / renewal / claim), ya general chat hai.
    Yahi mechanism user ko ek flow se doosri flow mein 'jump' karne deta hai.
    """
    from agent.graph import router_model, general_model

    history = _clean_history(state.text)

    decision = await router_model.ainvoke([
        SystemMessage(content=orchestrator_prompt.format(current_flow=state.current_flow or "none")),
        *history,
    ])

    flow = decision.flow

    # General chat — orchestrator khud reply karti hai, kisi flow mein nahi jaati
    if flow == "general":
        reply = await general_model.ainvoke([
            SystemMessage(content=general_prompt),
            *history,
        ])
        return {"text": [reply], "current_flow": None}

    # Warna sirf current_flow set karo — conditional edge isi ke hisaab se flow bot pe bhej degi
    return {"current_flow": flow}
