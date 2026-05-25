from langchain_core.runnables import RunnableConfig
from agent.db import engine,text

def gives_validity_and_next_bill_info(config:RunnableConfig):
    """
    it gonna return you details that include (valid from, valid upto, next_bill, policy_name, grace_period) of all the policies that user is having.

    """

    auth_user_id = config["configurable"]["auth_user_id"]
    with engine.connect() as conn:
        rows = conn.execute(text("""

        SELECT * FROM policyholder WHERE user_id = :auth_user_id
    
        """),{'user_id':auth_user_id}).fetchall()
        if not rows:
            return { "status": "no_policy_found",
            "user_has_policy": False,
            "message": "User does not currently hold any insurance policy."
            }
    policies = []

    for row in rows:

        row = dict(row._mapping)

        policies.append({
            "policy_id": row["policy_id"],
            "policy_name": row["policy_name"],
            "valid_from": str(row["valid_from"]),
            "next_bill": str(row["next_bill"]),
            "valid_upto": str(row["up_to"]),
            "grace_period_days": row["grace_period"]
        })
        
    return {
        "status": "success",
        "user_has_policy": True,
        "total_policies": len(policies),
        "policies": policies,
        "message": "you can ask the user that of which policy you want to get the details."
    }
