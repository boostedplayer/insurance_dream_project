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
    Jab user naya insurance policy explore ya kharidna chahta ho tab use karo.
    User ke profile pe ML-based risk scoring chalata hai aur top 3
    recommended policies return karta hai — risk loading ke baad personalized premiums ke saath.

    policy_type yeh teen mein se ek hona chahiye: health, motor, life
    """
    auth_user_id = config["configurable"]["auth_user_id"]

    if policy_type not in {"health", "motor", "life"}:
        return {"error": "Invalid policy_type. Must be one of: health, motor, life."}

    # ML model ke liye user ka demographics fetch karo
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

    # Profile complete hai? Risk scoring ke liye demographics zaroori hain.
    # Motor-specific fields (vehicle_*, mileage) ko health/life ke liye optional rakho.
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

    from agent.graph import ml_model  # circular import se bachne ke liye yahan import karo, module load ke time nahi
    # Model "Yes"/"No" strings pe trained hai, lekin DB inhe BOOLEAN store karta hai — convert karo
    for _col in ("smoker", "chronic_disease"):
        user_dict[_col] = "Yes" if user_dict.get(_col) else "No"
    # Motor fields agar NULL hain toh safe defaults (health/life inquiry mein matter nahi karte)
    for _col in ("vehicle_age", "driving_violations", "annual_mileage", "claims_history", "dependents"):
        if user_dict.get(_col) is None:
            user_dict[_col] = 0
    user_df = pd.DataFrame([user_dict])
    risk_score = float(ml_model.predict(user_df)[0])
    risk_category = get_risk_category(risk_score)
    loading_percent = RISK_LOADING[risk_category]

    # matching policies fetch karo
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

    # underwriting result save karo (inquiry level — abhi koi specific policy select nahi hui)
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
