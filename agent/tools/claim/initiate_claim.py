from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from agent.db.db import engine
from sqlalchemy import text
from datetime import date


@tool
def initiate_claim(
    holder_id: int,
    claim_type: str,
    incident_description: str,
    claimed_amount: float,
    config: RunnableConfig,
) -> dict:
    """
    Jab user insurance claim file karna chahta ho tab use karo.
    Yeh claims flow mein hamesha PEHLA step hai — assess_claim se pehle ise call karo.

    Examples: 'I want to file a claim', 'I had an accident', 'I was hospitalised',
              'my vehicle was damaged', 'I need to claim for my medical expenses'.

    holder_id            — jis policyholder ID ke under claim file karna hai.
                           Agar user ne nahi bataya toh get_user_policies use karo.
    claim_type           — claim ka type (e.g. 'medical_expense', 'hospitalisation',
                           'accident', 'theft', 'third_party_damage', 'critical_illness').
    incident_description — user ke apne shabdon mein kya hua tha.
    claimed_amount       — user kitna claim kar raha hai INR mein.
    Returns: claim_id jo agli step (assess_claim) mein kaam aayega.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    with engine.connect() as conn:
        holder = conn.execute(
            text("""
                SELECT ph.holder_id, ph.status, ph.valid_from, ph.up_to,
                       p.policy_name, p.policy_type, p.coverage_amount,
                       p.what_covers, p.what_doesnt_cover
                FROM policyholder ph
                JOIN policy p ON ph.policy_id = p.policy_id
                WHERE ph.holder_id = :hid AND ph.user_id = :uid
            """),
            {"hid": holder_id, "uid": auth_user_id}
        ).fetchone()

    if not holder:
        return {
            "status": "not_found",
            "agent_guidance": "Policyholder record not found. Call get_user_policies to get the correct holder_id."
        }

    holder = dict(holder._mapping)

    if holder["status"] == "cancelled":
        return {
            "status": "policy_cancelled",
            "policy_name": holder["policy_name"],
            "agent_guidance": f"Policy '{holder['policy_name']}' is cancelled. Claims cannot be filed on a cancelled policy."
        }

    today  = date.today()
    up_to  = holder["up_to"]
    # Expiry ke baad bhi 30 din ka grace period milta hai
    if hasattr(up_to, '__sub__') and (today - up_to).days > 30:
        return {
            "status": "policy_expired",
            "policy_name": holder["policy_name"],
            "expiry": str(up_to),
            "agent_guidance": (
                f"Policy '{holder['policy_name']}' expired on {up_to} and the grace period has passed. "
                "Claims cannot be filed. Suggest the user renew or purchase a new policy."
            )
        }

    with engine.begin() as conn:
        claim = conn.execute(
            text("""
                INSERT INTO claim
                    (holder_id, claim_type, claim_amount, incident_description, status)
                VALUES
                    (:hid, :ctype, :amount, :desc, 'initiated')
                RETURNING claim_id
            """),
            {
                "hid":    holder_id,
                "ctype":  claim_type,
                "amount": claimed_amount,
                "desc":   incident_description,
            }
        ).fetchone()

    claim_id = claim["claim_id"]

    return {
        "status":   "claim_initiated",
        "claim_id": claim_id,
        "policy": {
            "policy_name":     holder["policy_name"],
            "coverage_amount": str(holder["coverage_amount"]),
            "what_covers":     holder["what_covers"],
            "what_doesnt_cover": holder["what_doesnt_cover"],
        },
        "claim": {
            "claim_type":         claim_type,
            "claimed_amount":     claimed_amount,
            "incident_description": incident_description,
        },
        "agent_guidance": (
            f"Claim #{claim_id} has been initiated. "
            "Now call assess_claim with this claim_id to run the eligibility and risk assessment."
        )
    }
