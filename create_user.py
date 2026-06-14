"""
Seedha database mein ek test user banaata hai.
Registration fix hone tak ya testing ke liye chalao.

Usage:
    python create_user.py
"""
from dotenv import load_dotenv
load_dotenv()

from agent.db.db import engine
from sqlalchemy import text
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

NAME     = "Test User"
EMAIL    = "test@insurance.com"
PASSWORD = "password123"
CITY     = "Mumbai"

with engine.begin() as conn:
    existing = conn.execute(
        text("SELECT user_id FROM users WHERE email = :email"),
        {"email": EMAIL}
    ).fetchone()

    if existing:
        print(f"User already exists  →  email: {EMAIL}  |  password: {PASSWORD}")
    else:
        conn.execute(
            text("""
                INSERT INTO users (name, email, password_hash, city, is_active)
                VALUES (:name, :email, :pw, :city, true)
            """),
            {"name": NAME, "email": EMAIL, "pw": _pwd.hash(PASSWORD), "city": CITY}
        )
        print("✓ User created successfully!")
        print(f"  email    : {EMAIL}")
        print(f"  password : {PASSWORD}")
        print()
        print("  → http://localhost:8001/login/  pe jao aur login karo")
