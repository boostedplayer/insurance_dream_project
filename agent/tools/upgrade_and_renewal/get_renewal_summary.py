from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
from datetime import date


@tool
def get_renewal_summary(policy_name: str, config: RunnableConfig) -> dict:
    """
    use when user wants to renew an existing policy. call this before creating a renewal payment.
    shows current status, expiry date, and renewal premium upfront.
    policy_name: name of the policy to renew (from conversation or get_user_policies).
    returns holder_id, expiry, grace period status, and renewal premium.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT
                    ph.holder_id,
                    ph.valid_from,
                    ph.up_to,
                    ph.next_bill,
                    ph.grace_period,
                    ph.status,
                    p.policy_id,
                    p.policy_name,
                    p.policy_type,
                    p.base_premium,
                    p.coverage_amount,
                    p.policy_tenure
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.user_id = :uid
                  AND LOWER(p.policy_name) LIKE LOWER(:name)
                  AND ph.status = 'active'
                ORDER BY ph.holder_id DESC
                LIMIT 1
            """),
            {"uid": auth_user_id, "name": f"%{policy_name}%"}
        ).fetchone()

        if not row:
            return {
                "status": "policy_not_found",
                "agent_guidance": (
                    f"No active policy found matching '{policy_name}'. "
                    "Call get_user_policies to show the user their active policies first."
                )
            }

        row = dict(row._mapping)

        underwriting = conn.execute(
            text("""
                SELECT risk_category, loading_percent, risk_score
                FROM underwriting_results
                WHERE user_id = :uid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": auth_user_id}
        ).fetchone()

    today       = date.today()
    up_to       = row["up_to"]
    days_left   = (up_to - today).days if hasattr(up_to, '__sub__') else None

    # parse grace period string e.g. '30 days' → 30
    grace_str   = str(row["grace_period"])
    grace_days  = 30  # default fallback
    try:
        grace_days = int(grace_str.split()[0])
    except (ValueError, IndexError):
        pass

    in_grace        = days_left is not None and days_left < 0 and abs(days_left) <= grace_days
    renewal_blocked = days_left is not None and days_left < 0 and abs(days_left) > grace_days

    uw             = dict(underwriting._mapping) if underwriting else {"loading_percent": 0, "risk_category": "unknown", "risk_score": None}
    base_premium   = float(row["base_premium"])
    loading_pct    = float(uw["loading_percent"])
    loading_amount = round(base_premium * loading_pct / 100, 2)
    final_premium  = round(base_premium + loading_amount, 2)

    return {
        "status":     "renewal_eligible" if not renewal_blocked else "renewal_blocked",
        "holder_id":  row["holder_id"],
        "policy": {
            "policy_id":       row["policy_id"],
            "policy_name":     row["policy_name"],
            "policy_type":     row["policy_type"],
            "coverage_amount": str(row["coverage_amount"]),
            "policy_tenure":   str(row["policy_tenure"]),
        },
        "current_validity": {
            "valid_from": str(row["valid_from"]),
            "up_to":      str(up_to),
            "next_bill":  str(row["next_bill"]),
            "days_left":  days_left,
            "in_grace_period": in_grace,
        },
        "renewal_pricing": {
            "base_premium":    base_premium,
            "risk_category":   uw["risk_category"],
            "loading_percent": loading_pct,
            "loading_amount":  loading_amount,
            "final_premium":   final_premium,
            "currency":        "INR",
        },
        "agent_guidance": (
            f"Show the user their renewal summary for '{row['policy_name']}'.\n"
            f"  Current expiry:  {up_to}  ({days_left} days left)\n"
            f"  In grace period: {in_grace}\n"
            f"  Renewal premium: ₹{final_premium} (base ₹{base_premium} + {loading_pct}% loading)\n\n"
            + ("Renewal is BLOCKED — policy has crossed grace period." if renewal_blocked else
               "Ask: 'Would you like to proceed to renewal payment?' If yes, call create_renewal_payment with holder_id.")
        )
    }
