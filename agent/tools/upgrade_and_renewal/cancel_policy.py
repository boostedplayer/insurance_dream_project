from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def cancel_policy(holder_id: int, reason: str, config: RunnableConfig) -> dict:
    """
    Tab use karo jab user seedha kisi existing policy ko cancel ya exit karna chahta ho.
    Isse call karne se pehle user se confirm zaroor karo — cancellation wapas nahi hoti.

    Examples: 'cancel my policy', 'I want to exit my health insurance',
              'discontinue my motor cover', 'I don't need this policy anymore'.

    holder_id — jo policyholder cancel karna hai uska ID (get_user_policies se lo).
    reason    — cancellation ki wajah thodi si (user ke words ya tumhari summary).
    Returns: cancellation ka confirmation.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT ph.holder_id, ph.status, p.policy_name, ph.up_to
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.holder_id = :hid AND ph.user_id = :uid
            """),
            {"hid": holder_id, "uid": auth_user_id}
        ).fetchone()

    if not row:
        return {
            "status": "not_found",
            "agent_guidance": "Policyholder record not found. Verify holder_id with get_user_policies."
        }

    row = dict(row._mapping)

    if row["status"] == "cancelled":
        return {
            "status":      "already_cancelled",
            "policy_name": row["policy_name"],
            "agent_guidance": f"Policy '{row['policy_name']}' is already cancelled."
        }

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE policyholder
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE holder_id = :hid AND user_id = :uid
            """),
            {"hid": holder_id, "uid": auth_user_id}
        )

        # Internal record ke liye reason support_tickets mein log karo
        conn.execute(
            text("""
                INSERT INTO support_tickets (user_id, reason, context, status)
                VALUES (:uid, 'Policy cancellation', :ctx, 'closed')
            """),
            {
                "uid": auth_user_id,
                "ctx": f"User cancelled policy '{row['policy_name']}' (holder_id={holder_id}). Reason: {reason}",
            }
        )

    return {
        "status":       "cancelled",
        "policy_name":  row["policy_name"],
        "cancelled_at": "now",
        "agent_guidance": (
            f"Policy cancelled. Tell the user:\n"
            f"'Your {row['policy_name']} has been cancelled successfully. "
            "You will not be charged further. If you change your mind, you can purchase a new policy anytime. "
            "We're sorry to see you go — is there anything we could have done better?'"
        )
    }
