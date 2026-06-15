from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def escalate_to_support(reason: str, context: str, config: RunnableConfig) -> dict:
    """
    use when user wants a human agent or the query is too complex for the bot.
    reason: one-line why escalation is needed (you generate this).
    context: short summary of the relevant conversation (you generate this).
    creates a support ticket and returns the ticket id.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO support_tickets (user_id, reason, context, status)
                VALUES (:user_id, :reason, :context, 'open')
                RETURNING ticket_id, created_at
            """),
            {
                "user_id": auth_user_id,
                "reason":  reason,
                "context": context,
            }
        ).fetchone()

    # SQLAlchemy 2.0 Row can't be indexed by string key — use ._mapping
    # this was silently breaking escalation before
    result     = dict(result._mapping)
    ticket_id  = result["ticket_id"]
    created_at = str(result["created_at"])

    return {
        "status":     "ticket_created",
        "ticket_id":  ticket_id,
        "created_at": created_at,
        "agent_guidance": (
            f"Tell the user their support ticket #{ticket_id} has been created. "
            "A human agent will reach out to them shortly on their registered contact details. "
            "Assure them their concern has been noted and will be addressed. "
            "Do not promise a specific resolution time unless you know it."
        )
    }
