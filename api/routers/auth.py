from fastapi import APIRouter, HTTPException, Depends, status
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from agent.db.db import engine
from sqlalchemy import text
from api.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse, UserProfile,
    ProfileFull, ProfileUpdate,
)
from api.dependencies import get_current_user
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
    payload = {"sub": str(user_id), "email": email, "exp": expire}  # sub string hona zaroori hai (JWT spec + python-jose)
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
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT user_id, name, email, password_hash, is_active FROM users WHERE email = :email"),
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
    )


@router.get("/me", response_model=UserProfile)
def me(user: dict = Depends(get_current_user)):
    return UserProfile(**user)


_PROFILE_FIELDS = [
    "age", "gender", "income_category", "occupation", "smoker",
    "alcohol_consumption", "bmi", "exercise_frequency", "chronic_disease",
    "claims_history", "marital_status", "dependents", "vehicle_age",
    "driving_violations", "annual_mileage",
]


@router.get("/profile", response_model=ProfileFull)
def get_profile(user: dict = Depends(get_current_user)):
    """Poora user profile laao — demographics ke saath (profile page ke liye)."""
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
    """Profile update karo — sirf woh fields jo bheje gaye hain (None ko skip karo)."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE users SET {set_clause} WHERE user_id = :uid"),
                {**updates, "uid": user["user_id"]}
            )

    # Updated profile wapas laao
    cols = "user_id, name, email, city, " + ", ".join(_PROFILE_FIELDS)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {cols} FROM users WHERE user_id = :uid"),
            {"uid": user["user_id"]}
        ).fetchone()
    return ProfileFull(**dict(row._mapping))
