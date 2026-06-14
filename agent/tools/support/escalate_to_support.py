from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def escalate_to_support(reason: str, context: str, config: RunnableConfig) -> dict:
    """
    Tab use karo jab user kisi human agent se baat karna chahta ho, ya query itni complex ho
    ki bot se solve nahi ho rahi, ya user frustrated ho aur use insaani madad chahiye.
    Examples: 'I want to talk to someone', 'connect me to an agent',
              'this is not helping, I need a real person', 'I have a complaint.'

    reason  — ek line mein batao kyun escalation ki zarurat hai (yeh tum generate karo).
    context — conversation ka short summary jo issue se related ho (yeh bhi tum generate karo).

    Support ticket banata hai aur user ke reference ke liye ek ticket ID return karta hai.
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
