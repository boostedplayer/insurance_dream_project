from fastapi import APIRouter, HTTPException, Depends, status
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from agent.db.db import engine
from sqlalchemy import text
from api.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse, UserProfile,
    ProfileFull, ProfileUpdate, QuestionnaireSubmit, QuestionnaireStatus,
)
from api.dependencies import get_current_user
from api.questionnaire_data import (
    QUESTIONS, MAPPED_FIELDS, validate_answers, map_answers_to_profile,
)
import json
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET       = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM    = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", 24))

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _make_token(user_id: int, email: str) -> str:
    expire  = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "email": email, "exp": expire}  # sub must be a string (JWT spec + python-jose)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": body.email}
        ).fetchone()

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = _pwd.hash(body.password)

    with engine.begin() as conn:
        row = dict(conn.execute(
            text("""
                INSERT INTO users (name, email, password_hash, city, is_active)
                VALUES (:name, :email, :pw, :city, true)
                RETURNING user_id, name
            """),
            {"name": body.name, "email": body.email, "pw": hashed, "city": body.city}
        ).fetchone()._mapping)

    return TokenResponse(
        access_token=_make_token(row["user_id"], body.email),
        user_id=row["user_id"],
        name=row["name"],
        risk_profile_completed=False,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT user_id, name, email, password_hash, is_active, risk_profile_completed FROM users WHERE email = :email"),
            {"email": body.email}
        ).fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = dict(user._mapping)

    if not user["password_hash"] or not _pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return TokenResponse(
        access_token=_make_token(user["user_id"], user["email"]),
        user_id=user["user_id"],
        name=user["name"],
        risk_profile_completed=bool(user.get("risk_profile_completed")),
    )


@router.get("/me", response_model=UserProfile)
def me(user: dict = Depends(get_current_user)):
    return UserProfile(**user)


# onboarding questionnaire

@router.get("/questionnaire")
def get_questionnaire():
    """canonical list of 30 MCQ questions for the frontend."""
    return {"questions": QUESTIONS}


@router.get("/questionnaire/status", response_model=QuestionnaireStatus)
def questionnaire_status(user: dict = Depends(get_current_user)):
    """check if user completed the onboarding questionnaire."""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT risk_score, risk_category
                FROM risk_questionnaire_responses
                WHERE user_id = :uid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": user["user_id"]}
        ).fetchone()
    row = dict(row._mapping) if row else {}
    return QuestionnaireStatus(
        completed=bool(user.get("risk_profile_completed")),
        risk_score=row.get("risk_score"),
        risk_category=row.get("risk_category"),
    )


@router.post("/questionnaire", response_model=QuestionnaireStatus, status_code=status.HTTP_201_CREATED)
def submit_questionnaire(body: QuestionnaireSubmit, user: dict = Depends(get_current_user)):
    """
    receive 30-MCQ answers: validate → store raw answers → update user profile
    → run ML risk score → save underwriting result → mark profile completed.
    """
    uid = user["user_id"]
    answers = body.answers or {}

    problems = validate_answers(answers)
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems[:5]))

    profile = map_answers_to_profile(answers)

    # best-effort ML score — don't block onboarding if model fails
    # IMPORTANT: pipeline uses remainder='passthrough', so DataFrame columns must match
    # training CSV order exactly — otherwise numeric features get misaligned.
    # new_policy_inquiry uses the same order.
    _FEATURE_ORDER = [
        "age", "gender", "income_category", "occupation", "smoker",
        "alcohol_consumption", "bmi", "exercise_frequency", "chronic_disease",
        "claims_history", "marital_status", "dependents", "vehicle_age",
        "driving_violations", "annual_mileage", "city",
    ]
    risk_score = None
    risk_category = None
    try:
        import pandas as pd
        from agent.graph import ml_model
        from agent.nodes.utils import get_risk_category, RISK_LOADING

        model_row = dict(profile)
        # model expects "Yes"/"No" strings, not booleans
        for col in ("smoker", "chronic_disease"):
            model_row[col] = "Yes" if model_row.get(col) else "No"
        # safe defaults for optional fields
        for col in ("vehicle_age", "driving_violations", "annual_mileage",
                    "claims_history", "dependents"):
            model_row.setdefault(col, 0)
        df = pd.DataFrame([{c: model_row.get(c) for c in _FEATURE_ORDER}],
                          columns=_FEATURE_ORDER)
        risk_score = float(ml_model.predict(df)[0])
        risk_category = get_risk_category(risk_score)
        loading_percent = RISK_LOADING[risk_category]
    except Exception:
        loading_percent = None

    with engine.begin() as conn:
        # only whitelisted mapped columns
        safe = {k: v for k, v in profile.items() if k in MAPPED_FIELDS}
        if safe:
            set_clause = ", ".join(f"{k} = :{k}" for k in safe)
            conn.execute(
                text(f"UPDATE users SET {set_clause} WHERE user_id = :uid"),
                {**safe, "uid": uid},
            )

        conn.execute(
            text("""
                INSERT INTO risk_questionnaire_responses
                    (user_id, answers, risk_score, risk_category)
                VALUES (:uid, CAST(:answers AS JSONB), :rs, :rc)
            """),
            {
                "uid": uid,
                "answers": json.dumps(answers),
                "rs": risk_score,
                "rc": risk_category,
            },
        )

        # store underwriting result so agent can suggest insurance immediately
        if risk_score is not None and loading_percent is not None:
            conn.execute(
                text("""
                    INSERT INTO underwriting_results
                        (user_id, risk_score, risk_category, loading_percent)
                    VALUES (:uid, :rs, :rc, :lp)
                """),
                {"uid": uid, "rs": risk_score, "rc": risk_category, "lp": loading_percent},
            )

        conn.execute(
            text("UPDATE users SET risk_profile_completed = true WHERE user_id = :uid"),
            {"uid": uid},
        )

    return QuestionnaireStatus(
        completed=True,
        risk_score=risk_score,
        risk_category=risk_category,
    )


_PROFILE_FIELDS = [
    "age", "gender", "income_category", "occupation", "smoker",
    "alcohol_consumption", "bmi", "exercise_frequency", "chronic_disease",
    "claims_history", "marital_status", "dependents", "vehicle_age",
    "driving_violations", "annual_mileage",
]


@router.get("/profile", response_model=ProfileFull)
def get_profile(user: dict = Depends(get_current_user)):
    """fetch full user profile including demographics."""
    cols = "user_id, name, email, city, " + ", ".join(_PROFILE_FIELDS)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {cols} FROM users WHERE user_id = :uid"),
            {"uid": user["user_id"]}
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return ProfileFull(**dict(row._mapping))


@router.put("/profile", response_model=ProfileFull)
def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    """partial update — only fields that were sent (skip None)."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE users SET {set_clause} WHERE user_id = :uid"),
                {**updates, "uid": user["user_id"]}
            )

    cols = "user_id, name, email, city, " + ", ".join(_PROFILE_FIELDS)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {cols} FROM users WHERE user_id = :uid"),
            {"uid": user["user_id"]}
        ).fetchone()
    return ProfileFull(**dict(row._mapping))
