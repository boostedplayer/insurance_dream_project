from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def cancel_policy(holder_id: int, reason: str, config: RunnableConfig) -> dict:
    """
    use when user wants to cancel an existing policy. always confirm with user first — irreversible.
    holder_id: the policyholder id to cancel (get from get_user_policies).
    reason: brief reason in user's words or your summary.
    returns cancellation confirmation.
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

        # log reason to support_tickets for internal record
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
