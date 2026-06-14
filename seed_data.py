"""
Ek baar chalao — Postgres ko zaroori data se seed karta hai:
  1. `policy` table  ← insurance_policy_dataset.csv se
  2. test user ka poora ML profile (taaki risk scoring chal sake)

Usage:
    python seed_data.py
"""
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from sqlalchemy import text
from agent.db.db import engine

CSV_PATH   = "insurance_policy_dataset.csv"
TEST_EMAIL = "test@insurance.com"


# ── 1. Policy table seed karo ──────────────────────────────────────────────────

def seed_policies():
    df = pd.read_csv(CSV_PATH)
    print(f"CSV se {len(df)} policies load hui")

    with engine.begin() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM policy")).scalar()
        if existing and existing > 0:
            print(f"policy table mein pehle se {existing} rows hain — seed skip kar rahe hain")
            return

        for _, r in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO policy
                        (policy_id, policy_name, policy_type, policy_description,
                         risk_category, policy_tenure, what_covers, what_doesnt_cover,
                         base_premium, coverage_amount)
                    VALUES
                        (:policy_id, :policy_name, :policy_type, :policy_description,
                         :risk_category, CAST(:policy_tenure AS INTERVAL), :what_covers, :what_doesnt_cover,
                         :base_premium, :coverage_amount)
                    ON CONFLICT (policy_id) DO NOTHING
                """),
                {
                    "policy_id":          int(r["policy_id"]),
                    "policy_name":        r["policy_name"],
                    "policy_type":        r["policy_type"],
                    "policy_description": r["policy_description"],
                    "risk_category":      r["risk_category"],
                    "policy_tenure":      str(r["policy_tenure"]),
                    "what_covers":        r["what_covers"],
                    "what_doesnt_cover":  r["what_does_not_cover"],
                    "base_premium":       float(r["base_premium"]),
                    "coverage_amount":    float(r["coverage_amount"]),
                }
            )
    print(f"[OK] {len(df)} policies seed ho gayi")


# ── 2. Test user ko poora ML profile do ────────────────────────────────────────
# Values training data (insurance_risk_dataset_5000.csv) ke known categories se li hain

def complete_test_user():
    profile = {
        "age": 35, "gender": "Male", "income_category": "Middle",
        "occupation": "Business Owner", "smoker": False, "alcohol_consumption": "Occasional",
        "bmi": 24.5, "exercise_frequency": "Rarely", "chronic_disease": False,
        "claims_history": 1, "marital_status": "Married", "dependents": 2,
        "vehicle_age": 0, "driving_violations": 0, "annual_mileage": 8000,
    }
    with engine.begin() as conn:
        user = conn.execute(
            text("SELECT user_id FROM users WHERE email = :e"), {"e": TEST_EMAIL}
        ).fetchone()
        if not user:
            print(f"[X] {TEST_EMAIL} user nahi mila — pehle 'python create_user.py' chalao")
            return
        conn.execute(
            text("""
                UPDATE users SET
                    age=:age, gender=:gender, income_category=:income_category,
                    occupation=:occupation, smoker=:smoker, alcohol_consumption=:alcohol_consumption,
                    bmi=:bmi, exercise_frequency=:exercise_frequency, chronic_disease=:chronic_disease,
                    claims_history=:claims_history, marital_status=:marital_status, dependents=:dependents,
                    vehicle_age=:vehicle_age, driving_violations=:driving_violations, annual_mileage=:annual_mileage
                WHERE email=:e
            """),
            {**profile, "e": TEST_EMAIL}
        )
    print(f"[OK] {TEST_EMAIL} ka poora ML profile set ho gaya")


if __name__ == "__main__":
    seed_policies()
    complete_test_user()
    print("\nDone! Ab chat mein 'explore health policies' kaam karega.")
