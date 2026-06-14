from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.graph import startup, shutdown
from api.routers import auth, chat, webhook, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()   # async pool khol do + checkpoint tables bana do
    yield
    await shutdown()  # exit pe pool band karo


app = FastAPI(
    title="Insurance Agentic AI — Backend API",
    description="FastAPI backend powering the LangGraph insurance agent. Consumed by Django frontend.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,    prefix="/api")
app.include_router(chat.router,    prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(admin.router,   prefix="/api")


@app.get("/")
async def health():
    return {"status": "ok", "service": "Insurance AI API"}
