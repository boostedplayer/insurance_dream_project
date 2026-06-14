from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy import text
from agent.db.db import engine
from api.schemas.chat import ChatRequest, ChatResponse
from api.dependencies import get_current_user
import agent.graph as _graph  # module reference — app is None until startup() runs
import uuid
import json

router = APIRouter(prefix="/chat", tags=["chat"])


def _touch_session(session_id: str, user_id: int, first_message: str) -> None:
    """
    Session ko chat_sessions table mein upsert karo. Agar nayi hai toh title
    pehle user message se banao (ChatGPT jaisa). updated_at hamesha refresh karo.
    """
    title = (first_message or "New chat").strip()
    if len(title) > 60:
        title = title[:57] + "..."
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO chat_sessions (session_id, user_id, title)
                VALUES (:sid, :uid, :title)
                ON CONFLICT (session_id)
                DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            """),
            {"sid": session_id, "uid": user_id, "title": title}
        )


def _content_to_text(content) -> str:
    """
    LLM message content ko plain string mein normalize karo.
    Gemini 3.x content ko blocks ki list mein deta hai — jaise
    [{'type': 'text', 'text': '...'}, {...thought signature...}] —
    Groq/OpenAI seedha string dete hain. Dono handle karo.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""


def _get_last_ai_text(result: dict) -> str:
    # Reverse se chalo aur pehla AIMessage dhoondo jiska text content actually ho —
    # tool-call-only messages (khaali text) ko skip kar do.
    for msg in reversed(result.get("text", [])):
        if isinstance(msg, AIMessage):
            text = _content_to_text(msg.content)
            if text.strip():
                return text
    return ""


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Main chat endpoint hai yeh. Message bhejo, agent ka jawab lo.
    Session history har session_id ke liye LangGraph ke async checkpointer se preserve hoti hai.
    """
    session_id = body.session_id or str(uuid.uuid4())
    user_id    = user["user_id"]

    config = {
        "configurable": {
            "thread_id":    session_id,
            "auth_user_id": user_id,
        }
    }

    state_input = {
        "text":         [HumanMessage(content=body.message)],
        "auth_user_id": user_id,
        "user_valid":   True,
    }

    _touch_session(session_id, user_id, body.message)

    result = await _graph.app.ainvoke(state_input, config=config)

    return ChatResponse(
        response=_get_last_ai_text(result),
        session_id=session_id,
        current_flow=result.get("current_flow"),
    )


@router.post("/stream")
async def chat_stream(body: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Server-Sent Events ke zariye streaming chat hoti hai yahan.
    Django ya frontend EventSource ya fetch + ReadableStream se consume kar sakta hai.
    """
    session_id = body.session_id or str(uuid.uuid4())
    user_id    = user["user_id"]

    config = {
        "configurable": {
            "thread_id":    session_id,
            "auth_user_id": user_id,
        }
    }

    state_input = {
        "text":         [HumanMessage(content=body.message)],
        "auth_user_id": user_id,
        "user_valid":   True,
    }

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        async for chunk in _graph.app.astream(state_input, config=config, stream_mode="values"):
            for msg in chunk.get("text", []):
                if isinstance(msg, AIMessage):
                    txt = _content_to_text(msg.content)
                    if txt.strip():
                        payload = json.dumps({"type": "token", "content": txt})
                        yield f"data: {payload}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/history/{session_id}")
async def chat_history(session_id: str, user: dict = Depends(get_current_user)):
    """
    Diye gaye session ki poori conversation history wapas laao.
    """
    config = {"configurable": {"thread_id": session_id, "auth_user_id": user["user_id"]}}
    state  = await _graph.app.aget_state(config)

    if not state or not state.values:
        return {"session_id": session_id, "messages": []}

    messages = []
    for msg in state.values.get("text", []):
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user",      "content": _content_to_text(msg.content)})
        elif isinstance(msg, AIMessage):
            txt = _content_to_text(msg.content)
            if txt.strip():  # tool-call-only messages history mein mat dikhao
                messages.append({"role": "assistant", "content": txt})

    return {"session_id": session_id, "messages": messages}


# ── Chat sessions (sidebar) ─────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    """Current user ke saare chat sessions — newest first (sidebar ke liye)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT session_id, title, updated_at
                FROM chat_sessions
                WHERE user_id = :uid
                ORDER BY updated_at DESC
            """),
            {"uid": user["user_id"]}
        ).fetchall()

    return {
        "sessions": [
            {
                "session_id": r._mapping["session_id"],
                "title":      r._mapping["title"],
                "updated_at": r._mapping["updated_at"].isoformat() if r._mapping["updated_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/sessions")
async def create_session(user: dict = Depends(get_current_user)):
    """Naya khaali chat session banao aur uska id wapas do."""
    session_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO chat_sessions (session_id, user_id, title)
                VALUES (:sid, :uid, 'New chat')
            """),
            {"sid": session_id, "uid": user["user_id"]}
        )
    return {"session_id": session_id, "title": "New chat"}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Ek chat session delete karo (sirf apna)."""
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM chat_sessions WHERE session_id = :sid AND user_id = :uid"),
            {"sid": session_id, "uid": user["user_id"]}
        )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}
