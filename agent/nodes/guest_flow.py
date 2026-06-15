from sqlalchemy import text
from langchain_core.messages import AIMessage,SystemMessage,HumanMessage
from langgraph.graph import END
from langgraph.types import Command

from agent.prompts.validation_prompt import validation_prompt
from agent.graph import gc_model,info_validator,info_extractor
from agent.state.orchestration_state import OrchestrationState
from agent.state.user import User
from agent.db.db import engine


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


def check_user(state:OrchestrationState):

    with engine.connect() as conn:
       data = conn.execute(
            text("""
        SELECT * FROM users
        WHERE user_id = :user_id
            """),
        {"user_id":state.auth_user_id}
        )

       data = data.fetchone()

    if data:
        user_dict =dict(data._mapping)
        return {'user_valid':True, 'user_info':User(**user_dict)}
    else:
        return {"user_valid":False}


def _latest_messages(state: OrchestrationState):
    """walk back through history to find the latest human and ai messages."""
    latest_human_message = ""
    latest_model_message = ""
    for msg in reversed(state.text):
        if not latest_human_message and isinstance(msg, HumanMessage):
            latest_human_message = _as_text(msg.content)
        if not latest_model_message and isinstance(msg, AIMessage):
            latest_model_message = _as_text(msg.content)
        if latest_human_message and latest_model_message:
            break
    return latest_human_message, latest_model_message


# collection order and what to ask next
_NEXT_STAGE = {
    "greet":   "name",
    "name":    "email",
    "email":   "number",
    "number":  "pincode",
    "pincode": "done",
}

_ASK_INSTRUCTION = {
    "name":    "Politely ask the user for their full name so you can personalise the conversation.",
    "email":   "Thank the user for the detail they just gave, then politely ask for their email address.",
    "number":  "Thank the user for their email, then politely ask for their phone number.",
    "pincode": "Thank the user for their phone number, then politely ask for their area pincode.",
}


def guest_flow(state: OrchestrationState):
    """
    one step per user message: greet → name → email → number → pincode → login_popup.
    single state-machine node because separate nodes would loop without waiting for user input.
    """
    stage = state.guest_stage or "greet"

    # already done — don't save again, just nudge them to sign in
    if stage == "done":
        res = gc_model.invoke([
            SystemMessage(content=(
                "The user has already shared all their details. Warmly let them know that to "
                "continue — purchase a policy, file a claim or get personalised recommendations — "
                "they just need to sign in or create a free account using the buttons on the page."
            )),
            *state.text,
        ])
        return Command(update={"text": [res]}, goto=END)

    # first contact — greet and ask for name; don't consume the user's message (might be "hi" or a question)
    if stage == "greet":
        res = gc_model.invoke([
            SystemMessage(content=(
                "You are a friendly insurance assistant. Warmly welcome the user, briefly mention "
                "you'll need a few quick details to assist them, then ask for their full name. "
                "Keep it to 2 short sentences."
            )),
            *state.text,
        ])
        return Command(update={"text": [res], "guest_stage": "name"}, goto=END)

    # expecting an answer for the current stage field
    latest_human_message, latest_model_message = _latest_messages(state)

    output = info_extractor.invoke(latest_human_message)
    valid = info_validator.invoke(validation_prompt.format(
        model_ques=latest_model_message,
        user_ans=latest_human_message,
    ))

    if not valid.is_valid:
        # re-ask the same field
        res = gc_model.invoke([
            SystemMessage(content=(
                f"The user did not clearly provide their {stage}. Briefly acknowledge any concern "
                f"they raised and assure them you'll help right after a couple of details, then "
                f"politely ask again for their {stage}."
            )),
            *state.text,
        ])
        return Command(update={"text": [res]}, goto=END)

    # valid answer — store field and advance
    guest_info = state.guest_info.model_copy(update={stage: getattr(output, stage)})
    next_stage = _NEXT_STAGE.get(stage, "done")

    if next_stage == "done":
        # all details collected → save lead and show login popup
        return Command(
            update={"guest_info": guest_info, "guest_stage": "done"},
            goto="login_popup",
        )

    res = gc_model.invoke([
        SystemMessage(content=_ASK_INSTRUCTION[next_stage]),
        *state.text,
    ])
    return Command(
        update={"text": [res], "guest_info": guest_info, "guest_stage": next_stage},
        goto=END,
    )

def login_popup(state: OrchestrationState):
    info = state.guest_info
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO guest_leads (name, email, number, pincode)
                    VALUES (:name, :email, :number, :pincode)
                """),
                {
                    "name":    info.name,
                    "email":   info.email,
                    "number":  info.number,
                    "pincode": info.pincode,
                }
            )
    except Exception:
        pass  # don't let a db error kill the chat

    msg = AIMessage(content=(
        f"Thank you, {info.name or 'there'}! Your details have been saved. 🎉\n\n"
        "To access full insurance services — purchase a policy, file a claim, or manage renewals — "
        "please sign in or create a free account.\n\n"
        "👉 Click Sign In or Register at the top of the page to continue."
    ))
    return {"text": [msg]}
