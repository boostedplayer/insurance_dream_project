from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Any
import pandas as pd
from agent.db.db import engine
from sqlalchemy import text
from agent.nodes.utils import get_risk_category, RISK_LOADING


@tool
def new_policy_inquiry(policy_type: str, config: RunnableConfig) -> dict[str, Any]:
    """
    use when user wants to explore or buy a new policy.
    runs ML-based risk scoring on their profile and returns top 3 recommended policies with personalized premiums.
    policy_type must be one of: health, motor, life.
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    if policy_type not in {"health", "motor", "life"}:
        return {"error": "Invalid policy_type. Must be one of: health, motor, life."}

    # fetch user demographics for ML model
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT age, gender, income_category, occupation, smoker,
                       alcohol_consumption, bmi, exercise_frequency,
                       chronic_disease, claims_history, marital_status,
                       dependents, vehicle_age, driving_violations,
                       annual_mileage, city
                FROM users
                WHERE user_id = :user_id
            """),
            {"user_id": auth_user_id}
        ).fetchone()

    if row is None:
        return {"error": "User profile not found. Cannot calculate risk score."}

    user_dict = dict(row._mapping)

    # motor-specific fields (vehicle_*, mileage) are optional for health/life
    required = ["age", "gender", "income_category", "occupation", "bmi",
                "exercise_frequency", "alcohol_consumption", "marital_status", "city"]
    missing = [f for f in required if user_dict.get(f) in (None, "")]
    if missing:
        return {
            "status": "profile_incomplete",
            "missing_fields": missing,
            "agent_guidance": (
                "The user's profile is missing details needed to calculate a personalized premium "
                f"({', '.join(missing)}). Politely ask them to complete their profile by clicking the "
                "profile link (👤 their name) in the sidebar, then try again. Do not invent a risk score."
            ),
        }

    from agent.graph import ml_model  # late import to avoid circular dep
    # model trained on "Yes"/"No" strings but DB stores booleans — convert
    for _col in ("smoker", "chronic_disease"):
        user_dict[_col] = "Yes" if user_dict.get(_col) else "No"
    # motor fields default to 0 if null (don't matter for health/life)
    for _col in ("vehicle_age", "driving_violations", "annual_mileage", "claims_history", "dependents"):
        if user_dict.get(_col) is None:
            user_dict[_col] = 0
    user_df = pd.DataFrame([user_dict])
    risk_score = float(ml_model.predict(user_df)[0])
    risk_category = get_risk_category(risk_score)
    loading_percent = RISK_LOADING[risk_category]

    # fetch matching policies
    with engine.connect() as conn:
        policies = conn.execute(
            text("""
                SELECT policy_id, policy_name, policy_description,
                       policy_tenure, base_premium, coverage_amount, what_covers
                FROM policy
                WHERE risk_category = :risk_category
                  AND policy_type = :policy_type
                LIMIT 3
            """),
            {"risk_category": risk_category, "policy_type": policy_type}
        ).fetchall()

    if not policies:
        return {
            "message": f"No {policy_type} policies found for risk category '{risk_category}'.",
            "user_risk_profile": {"risk_score": round(risk_score, 2), "risk_category": risk_category},
        }

    recommended = []
    for p in policies:
        p = dict(p._mapping)
        base = float(p["base_premium"] or 0)
        loading_amount = round(base * loading_percent, 2)
        final_premium = round(base + loading_amount, 2)
        recommended.append({
            "policy_id":           p["policy_id"],
            "policy_name":         p["policy_name"],
            "policy_description":  p["policy_description"],
            "policy_tenure":       str(p["policy_tenure"]),
            "base_premium":        base,
            "risk_loading_percent": loading_percent * 100,
            "loading_amount":      loading_amount,
            "final_premium":       final_premium,
            "coverage_amount":     str(p["coverage_amount"]),
            "what_covers":         p["what_covers"],
        })

    # save underwriting result at inquiry level — no specific policy chosen yet
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO underwriting_results
                    (user_id, risk_score, risk_category, loading_percent)
                VALUES
                    (:user_id, :risk_score, :risk_category, :loading_percent)
            """),
            {
                "user_id":        auth_user_id,
                "risk_score":     risk_score,
                "risk_category":  risk_category,
                "loading_percent": loading_percent,
            }
        )

    return {
        "user_risk_profile": {
            "risk_score":    round(risk_score, 2),
            "risk_category": risk_category,
        },
        "recommended_policies": recommended,
    }
