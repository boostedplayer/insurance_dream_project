# Insurance Agentic AI

A full-stack conversational AI insurance platform powered by **LangGraph**, **Google Gemini**, and **FastAPI**. Users can inquire about, purchase, renew, and claim insurance policies through a natural-language agent that orchestrates specialized flows backed by real tools, ML risk scoring, and payment processing.

---

## Features

### For Authenticated Users
- **Policy management** — view active policies, premium breakdowns, validity, and billing info
- **Personalized quotes** — ML risk model (RandomForest) personalizes premiums based on a 30-MCQ onboarding questionnaire
- **Policy purchase** — end-to-end purchase with Razorpay payment integration
- **Claims** — file, track, and receive AI-assisted claim assessments with human-escalation support
- **Renewals & upgrades** — renew expiring policies or upgrade coverage tier

### For Guest Users
- Browse policies, FAQ, and coverage info via conversational Q&A
- Lead collection (name, email, phone, pincode) before prompting login

### For Admins
- Dashboard for all claims and support tickets
- Approve/reject claims manually
- Flag suspicious claims for human review

---

## Architecture

```
User (Browser)
    │
    ▼
Django Frontend  (port 8000)
    │  Login · Register · Chat UI · Questionnaire · Admin Dashboard
    │
    ▼
FastAPI Backend  (port 8002)
    │  Auth (JWT) · Chat · Admin · Razorpay Webhooks
    │
    ▼
LangGraph Agent  (StateGraph)
    ├── Orchestrator          ← intent classification (Gemini structured output)
    ├── Support Flow          ← policy Q&A, FAQ, claims history   (9 tools)
    ├── Purchase Flow         ← buy new policy                    (3 tools)
    ├── Claim Flow            ← file / track claims               (6 tools)
    ├── Renewal Flow          ← renew / upgrade policy            (8 tools)
    └── Guest Flow            ← lead collection (no login needed)
    │
    ▼
External Services
    ├── PostgreSQL 15         ← users, policies, claims, sessions
    ├── Pinecone              ← FAQ & policy vector search (RAG)
    ├── HuggingFace           ← sentence-transformers embeddings
    └── Razorpay              ← payment orders & webhooks
```

### Chat Flow (Authenticated)
1. User message → `POST /api/chat`
2. JWT extracted → user loaded from PostgreSQL
3. Orchestrator classifies intent via Gemini structured output
4. Routes to the appropriate flow node (support / purchase / claim / renewal)
5. Flow node calls domain-specific tools (DB queries, Razorpay, Pinecone RAG)
6. Gemini formats tool results into a conversational response
7. Conversation state persisted via `AsyncPostgresSaver` (LangGraph checkpointer)

### Guest Flow
Stateful multi-turn lead collection: greet → name → email → phone → pincode → show login prompt.

### Risk Scoring & Pricing
1. User answers 30 MCQs (age, income, BMI, smoker status, etc.)
2. Answers mapped to ML features → RandomForest predicts `risk_score` (0–100)
3. Score bucketed into tier (`very_low` / `low` / `medium` / `high` / `very_high`)
4. `final_premium = base_premium × (1 + loading_percent)` — unique per user

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.0 Flash (`ChatGoogleGenerativeAI`) |
| Agent Framework | LangGraph 0.2+ (StateGraph, AsyncPostgresSaver) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | Pinecone |
| API Backend | FastAPI 0.115+ · Uvicorn |
| Frontend | Django 5.0 · Gunicorn · HTML/CSS/JS templates |
| Database | PostgreSQL 15 · SQLAlchemy ORM · psycopg3 async |
| Auth | JWT (`python-jose`) · bcrypt |
| Payments | Razorpay 1.4+ |
| ML | scikit-learn RandomForestRegressor · pandas · joblib |
| Deployment | Docker · Docker Compose |
| Python | 3.11 |

---

## Project Structure

```
insurance_agentic_ai/
├── agent/
│   ├── graph.py                  # LangGraph StateGraph builder
│   ├── db/db.py                  # SQLAlchemy schema & engine
│   ├── nodes/                    # Graph nodes
│   │   ├── orchestrator.py       # Intent router
│   │   ├── auth_flow.py          # Authenticated support node
│   │   ├── guest_flow.py         # Guest lead collection
│   │   ├── purchase_flow.py      # Policy purchase
│   │   ├── renewal_flow.py       # Renewal & upgrade
│   │   ├── claim_flow.py         # Claims processing
│   │   └── condition.py          # Conditional routing helpers
│   ├── prompts/                  # Gemini system prompts per flow
│   ├── state/                    # Pydantic state models
│   ├── tools/
│   │   ├── support/              # 9 support tools
│   │   ├── purchase/             # 3 purchase tools
│   │   ├── claim/                # 6 claim tools
│   │   └── upgrade_and_renewal/  # 8 renewal/upgrade tools
│   └── vector/                   # Pinecone setup scripts
├── api/
│   ├── main.py                   # FastAPI app, CORS, lifespan, routers
│   ├── dependencies.py           # JWT auth middleware
│   ├── questionnaire_data.py     # 30-MCQ questions + feature mapping
│   └── routers/
│       ├── auth.py               # Register, login, questionnaire
│       ├── chat.py               # Chat, guest chat, session history
│       ├── webhook.py            # Razorpay payment webhooks
│       └── admin.py              # Claims & tickets dashboard
├── frontend/
│   └── chat/
│       ├── views.py              # Django views
│       └── templates/            # HTML templates (chat, login, admin, profile)
├── model.py                      # RandomForest training script
├── best_mode2.pk1                # Trained risk model (26 MB)
├── insurance_policy_dataset.csv  # 64 policies × 7 risk tiers
├── insurance_faq_dataset.csv     # 56 FAQ items for Pinecone
├── insurance_risk_dataset_5000.csv # 5000 samples for model training
├── create_user.py                # One-time: create test user
├── seed_data.py                  # One-time: seed policies + test user data
├── setup_vectors.py              # One-time: embed FAQ/policies → Pinecone
├── run.py                        # Start FastAPI dev server
├── run_django.py                 # Start Django dev server
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Profiles, demographics, risk fields |
| `policy` | 64 policy definitions across 7 risk tiers |
| `policyholder` | User–policy binding with validity & grace periods |
| `underwriting_results` | ML risk scores, loading %, premiums per user |
| `purchase_orders` | Razorpay orders + payment status |
| `claim` | Claim lifecycle (initiated → assessed → approved/rejected) |
| `support_tickets` | Escalated support requests |
| `chat_sessions` | Session metadata per user |
| `guest_leads` | Pre-login lead contact info |
| `risk_questionnaire_responses` | Raw 30-MCQ answers (audit trail) |

---

## API Endpoints

### Auth — `/api/auth/`
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create account |
| POST | `/login` | Authenticate, returns JWT |
| GET | `/me` | Current user profile |
| GET | `/questionnaire/status` | Risk assessment status |
| POST | `/questionnaire/submit` | Submit MCQs, compute risk score |

### Chat — `/api/chat/`
| Method | Path | Description |
|---|---|---|
| POST | `/` | Send message (authenticated) |
| POST | `/guest` | Send message (guest) |
| GET | `/sessions` | List user sessions |
| POST | `/sessions` | Create new session |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/history/{session_id}` | Conversation history |
| POST | `/stream` | SSE streaming endpoint |

### Admin — `/api/admin/`
| Method | Path | Description |
|---|---|---|
| GET | `/claims` | All claims |
| GET | `/tickets` | All support tickets |
| POST | `/claims/{id}/approve` | Approve claim |
| POST | `/claims/{id}/reject` | Reject claim |

### Webhook — `/api/webhook/`
| Method | Path | Description |
|---|---|---|
| POST | `/razorpay` | Razorpay payment notifications |

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 15
- Accounts & API keys for: Google AI Studio (Gemini), HuggingFace, Pinecone, Razorpay

### 1. Clone & configure environment

```bash
cd "insurance agentic ai"
cp .env.example .env
# Fill in all values in .env (see Environment Variables section below)
```

### 2. Install dependencies

```bash
python -m venv env
# Windows:
env\Scripts\activate
# macOS/Linux:
source env/bin/activate

pip install -r requirements.txt
```

### 3. Set up the database

Ensure PostgreSQL is running on `localhost:5432`. Tables are auto-created on first FastAPI startup via SQLAlchemy.

### 4. One-time data setup

Run these scripts once after the database is ready:

```bash
python create_user.py      # Create test user (test@insurance.com)
python seed_data.py        # Load 64 policies + complete test user profile
python setup_vectors.py    # Embed FAQ & policies into Pinecone
```

### 5. Start the servers

Open two terminals:

```bash
# Terminal 1 — FastAPI backend
python run.py
# Available at http://localhost:8002
# API docs at  http://localhost:8002/docs

# Terminal 2 — Django frontend
python run_django.py
# Available at http://localhost:8000
```

### Docker (alternative)

```bash
docker-compose up --build
```

Services: FastAPI on `:8002`, Django on `:8000`, PostgreSQL on `:5432`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Google Gemini
GEMINI_API_KEY=your_gemini_api_key

# HuggingFace (for embeddings)
HUGGINGFACEHUB_ACCESS_TOKEN=your_hf_token

# Pinecone
PINECONE_API_KEY=your_pinecone_key

# PostgreSQL
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/insurance_database

# JWT
JWT_SECRET=a-long-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# Razorpay
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
RAZORPAY_CALLBACK_URL=http://localhost:8000/payment/callback/

# Django
DJANGO_SECRET_KEY=a-long-random-string
DJANGO_DEBUG=True
FASTAPI_BASE_URL=http://localhost:8002
```

---

## Retraining the Risk Model

The trained model is pre-built at `best_mode2.pk1`. To retrain on new data:

```bash
python model.py
# Reads insurance_risk_dataset_5000.csv
# Outputs best_mode2.pk1 via RandomizedSearchCV + KFold CV
```

---

## Agent Tools Reference

### Support (9 tools)
`get_user_policies` · `get_specific_policy_details` · `gives_validity_and_next_bill_info` · `get_premium_breakdown` · `get_claim_history` · `compare_policies` · `new_policy_inquiry` · `get_faq_answer` · `escalate_to_support`

### Purchase (3 tools)
`initiate_purchase` · `create_payment_order` · `confirm_purchase`

### Claims (6 tools)
`initiate_claim` · `assess_claim` · `approve_claim` · `flag_for_human_review` · `escalate_claim_to_crm` · `check_claim_status`

### Renewal & Upgrade (8 tools)
`get_renewal_summary` · `create_renewal_payment` · `confirm_renewal` · `get_upgrade_options` · `initiate_upgrade` · `create_upgrade_payment` · `confirm_upgrade` · `cancel_policy`
