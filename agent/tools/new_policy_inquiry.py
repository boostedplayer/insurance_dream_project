from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Any
import pandas as pd
from agent.db.db import engine
from sqlalchemy import text
from graph import ml_model
from agent.nodes.utils import get_risk_category
from agent.nodes.utils import RISK_LOADING


@tool
def new_policy_inquiry(policy_type : str, config : RunnableConfig) -> dict[str,Any]:
    """
    Use when the user wants to inquire about a new insurance policy.

    policy_type should be one of:
    - health
    - motor
    - life

    Returns the top 3 policy suggestions for that insurance type.
    """
    auth_user_id = config["configurable"]["auth_user_id"]
    if policy_type not in {"health", "motor", "life"}:
        return {
            "error":"Invalid policy_type. Use: health, motor, or life."
        }
    
    with engine.connect() as conn:

        data = conn.execute(text("""
        SELECT age,gender,income_category,occupation,smoker,alcohol_consumption,bmi,exercise_frequency,chronic_disease,claims_history,marital_status,dependents,vehicle_age,driving_violations, annual_mileage,city FROM users where user_id = :user_id
        """),{'user_id':auth_user_id})
        data = data.fetchone()
    
    if data is None:
        return {
            "error":"user not found"
        }
      
    user_df = pd.DataFrame([dict(data._mapping)])

    risk_score = ml_model.predict(user_df)[0]
    risk_category = get_risk_category(risk_score)


    with engine.connect() as conn:

        policies = conn.execute(text("""
        SELECT * FROM policy where policy_category = :risk_category and policy_type = :policy_type LIMIT 3
        """),{'risk_category':risk_category,'policy_type':policy_type})
        policies = policies.fetchall()
    
    if not policies:
        return {
            "message": f"No {policy_type} policies found for {risk_category} risk category"
        }

    loading_percent = RISK_LOADING[risk_category]

    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO underwriting_results (
                user_id,
                risk_score,
                risk_category,
                loading_percent
            )
            VALUES (
                :user_id,
                :risk_score,
                :risk_category,
                :loading_percent
            ) 
            """),
            {
                "user_id" : auth_user_id,
                "risk_score" : risk_score,
                "risk_category" : risk_category,
                "loading_percent": loading_percent,
                
            }
        )

        return {
        "user_risk_profile": {
            "risk_category": risk_category,
        },

        "recommended_policies": [
            {
                "policy_name": i.policy_name,
                "policy_id": i.policy_id,
                "base_premium": i.premium,
                "risk_loading_percent": loading_percent,
                "final_premium": round(i.premium+i.premium*loading_percent,2),
                "coverage_amount": i.coverage_amount,
                "covers": i.covers,
            }
            for i in policies
        ]
    }