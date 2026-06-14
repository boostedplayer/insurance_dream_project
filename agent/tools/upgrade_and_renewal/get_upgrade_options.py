from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text


@tool
def get_upgrade_options(holder_id: int, config: RunnableConfig) -> dict:
    """
    Jab user apni existing policy ko better wali mein upgrade karna chahta ho tab use karo.
    Same policy type ke saare available upgrade options dikhata hai jisme zyada coverage ya premium ho.

    Examples: 'I want to upgrade my health policy', 'what are my upgrade options?',
              'is there a better plan available?'.

    holder_id — policyholder ka ID (get_user_policies ya conversation context se milega).
    Returns: upgrade options ki list with pricing, taaki user choose kar sake.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        current = conn.execute(
            text("""
                SELECT ph.holder_id, p.policy_id, p.policy_name, p.policy_type,
                       p.base_premium, p.coverage_amount, p.risk_category
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.holder_id = :hid AND ph.user_id = :uid AND ph.status = 'active'
            """),
            {"hid": holder_id, "uid": auth_user_id}
        ).fetchone()

        if not current:
            return {
                "status": "not_found",
                "agent_guidance": "Policy holder not found. Use get_user_policies to fetch the correct holder_id."
            }

        current = dict(current._mapping)

        # Same type ki policies dhundo jinka base_premium zyada ho (upgrade ke candidates)
        options = conn.execute(
            text("""
                SELECT policy_id, policy_name, policy_type, base_premium,
                       coverage_amount, risk_category, policy_description,
                       what_covers, what_doesnt_cover
                FROM policy
                WHERE policy_type = :ptype
                  AND base_premium > :current_premium
                  AND policy_id   != :current_pid
                ORDER BY base_premium ASC
            """),
            {
                "ptype":           current["policy_type"],
                "current_premium": float(current["base_premium"]),
                "current_pid":     current["policy_id"],
            }
        ).fetchall()

        underwriting = conn.execute(
            text("""
                SELECT loading_percent, risk_category
                FROM underwriting_results
                WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    if not options:
        return {
            "status": "no_upgrades_available",
            "current_policy": current["policy_name"],
            "agent_guidance": (
                f"No higher-tier policies found for '{current['policy_type']}'. "
                "Tell the user they are already on the highest available plan for this type."
            )
        }

    uw          = dict(underwriting._mapping) if underwriting else {"loading_percent": 0, "risk_category": "unknown"}
    loading_pct = float(uw["loading_percent"])

    upgrade_list = []
    for opt in options:
        opt = dict(opt._mapping)
        base         = float(opt["base_premium"])
        loading_amt  = round(base * loading_pct / 100, 2)
        final        = round(base + loading_amt, 2)
        upgrade_list.append({
            "policy_id":          opt["policy_id"],
            "policy_name":        opt["policy_name"],
            "policy_description": opt["policy_description"],
            "coverage_amount":    str(opt["coverage_amount"]),
            "what_covers":        opt["what_covers"],
            "base_premium":       base,
            "loading_percent":    loading_pct,
            "final_premium":      final,
            "currency":           "INR",
        })

    return {
        "status": "options_available",
        "current_policy": {
            "holder_id":   current["holder_id"],
            "policy_name": current["policy_name"],
            "policy_type": current["policy_type"],
            "base_premium": float(current["base_premium"]),
        },
        "upgrade_options": upgrade_list,
        "agent_guidance": (
            f"Present {len(upgrade_list)} upgrade option(s) to the user. "
            "For each, show: policy name, coverage amount, final premium (with their risk loading applied). "
            "Ask which one they'd like to upgrade to, then call initiate_upgrade with holder_id and target policy name."
        )
    }
