from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234567890-=@localhost:5432/insurance_database"
)

engine = create_engine(DB_URL)

# engine.connect() → sirf connection kholta hai, manually commit karna padega
# engine.begin()   → connection + transaction dono kholta hai, exit pe auto-commit ho jaata hai

with engine.begin() as conn:
    print("Connected successfully!")

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            address       TEXT,
            email         TEXT UNIQUE NOT NULL,
            age           INTEGER,
            gender        TEXT,
            income_category TEXT,
            occupation    TEXT,
            smoker        BOOLEAN DEFAULT false,
            alcohol_consumption TEXT,
            bmi           FLOAT,
            exercise_frequency TEXT,
            chronic_disease BOOLEAN DEFAULT false,
            claims_history INTEGER DEFAULT 0,
            marital_status TEXT,
            dependents    INTEGER DEFAULT 0,
            vehicle_age   INTEGER,
            driving_violations INTEGER DEFAULT 0,
            annual_mileage INTEGER,
            city          TEXT,
            preliminary_desc VARCHAR(255),
            is_active     BOOLEAN NOT NULL DEFAULT true
        );
    """))

    # policy table — CSV columns aur tool expectations ke saath match kiya hua hai
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS policy (
            policy_id         SERIAL PRIMARY KEY,
            policy_name       TEXT NOT NULL,
            policy_type       TEXT NOT NULL,
            policy_description TEXT,
            risk_category     TEXT NOT NULL,
            policy_tenure     INTERVAL NOT NULL,
            what_covers       TEXT,
            what_doesnt_cover TEXT,
            base_premium      FLOAT,
            coverage_amount   DECIMAL(12, 2)
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS policyholder (
            holder_id   SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(user_id),
            policy_id   INTEGER REFERENCES policy(policy_id),
            valid_from  DATE NOT NULL,
            next_bill   DATE NOT NULL,
            up_to       DATE NOT NULL,
            grace_period INTERVAL NOT NULL
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS claim (
            claim_id     SERIAL PRIMARY KEY,
            holder_id    INTEGER REFERENCES policyholder(holder_id),
            fraud_score  INTEGER,
            claim_amount DECIMAL(10, 2),
            claim_type   TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            verdict      TEXT
        );
    """))

    # underwriting_results — policy fields nullable hain kyunki inquiry-level records mein
    # abhi koi policy select nahi hui hoti
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS underwriting_results (
            underwriting_id SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL,
            policy_id       INTEGER,
            risk_score      FLOAT NOT NULL,
            risk_category   VARCHAR(30) NOT NULL,
            base_premium    FLOAT,
            loading_percent FLOAT NOT NULL,
            loading_amount  FLOAT,
            final_premium   FLOAT,
            model_version   VARCHAR(20) DEFAULT 'v1',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            order_id              SERIAL PRIMARY KEY,
            user_id               INTEGER REFERENCES users(user_id),
            policy_id             INTEGER REFERENCES policy(policy_id),
            razorpay_order_id     TEXT UNIQUE,
            razorpay_payment_id   TEXT,
            amount_paise          INTEGER NOT NULL,
            currency              TEXT NOT NULL DEFAULT 'INR',
            status                TEXT NOT NULL DEFAULT 'pending',
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at               TIMESTAMP
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id   SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(user_id),
            reason      TEXT NOT NULL,
            context     TEXT,
            status      TEXT NOT NULL DEFAULT 'open',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS guest_leads (
            lead_id    SERIAL PRIMARY KEY,
            name       TEXT,
            email      TEXT,
            number     TEXT,
            pincode    TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))

    # ChatGPT-style sidebar ke liye — har user ke chat sessions ka index
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id  TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            title       TEXT NOT NULL DEFAULT 'New chat',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))

    # Purane deployments mein jo columns nahi hain unhe yahan add kar do
    conn.execute(text("ALTER TABLE policyholder ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'"))
    conn.execute(text("ALTER TABLE policyholder ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP"))
    conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS order_type TEXT NOT NULL DEFAULT 'purchase'"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS incident_description TEXT"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS assessed_amount DECIMAL(10,2)"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS approved_amount DECIMAL(10,2)"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS routing TEXT"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS escalation_ticket_id INTEGER"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS human_agent_notes TEXT"))
    conn.execute(text("ALTER TABLE claim ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT"))

    print("Tables ready.")
