from sqlalchemy import create_engine,text

#engine.connect() → just opens a connection
#engine.begin() → opens a connection + starts a transaction + auto-commit

engine = create_engine(
    "postgresql://postgres:1234567890-=@localhost:5432/insurance_database"
)

with engine.begin() as conn:
    print("Connected successfully!")
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            holder_id INTEGER,
            policy_id INTEGER,
            name TEXT NOT NULL, 
            address TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            age INTEGER NOT NULL,
            preliminary_desc VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            claim INTEGER
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS policy (
            policy_id SERIAL PRIMARY KEY,
            policy_type TEXT NOT NULL,
            policy_desc TEXT NOT NULL,
            policy_tenure INTERVAL NOT NULL, 
            covers TEXT NOT NULL
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS policyholder (
            holder_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            policy_id INTEGER REFERENCES policy(policy_id),
            valid_from DATE NOT NULL,    
            next_bill DATE NOT NULL,
            up_to DATE NOT NULL,
            grace_period INTERVAL NOT NULL 
        );
    """))
 
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS claim (
            claim_id SERIAL PRIMARY KEY,
            holder_id INTEGER REFERENCES policyholder(holder_id),
            fraud_score INTEGER NOT NULL,
            claim_amount DECIMAL(10,2) NOT NULL, 
            claim_type TEXT NOT NULL,
            status TEXT NOT NULL,
            verdict TEXT NOT NULL
        );
    """))
    
    print('table created')