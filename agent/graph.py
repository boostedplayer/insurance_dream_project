from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from agent.state.orchestration_state import OrchestrationState
from agent.state.user import GuestResponseExtract, GuestResponseValidate, RouteDecision
from agent.prompts.insurance_prompt import insurance_prompt  # nodes ke liye re-export kiya hua hai

import joblib
import os
from dotenv import load_dotenv

load_dotenv()

_gemini_key = os.getenv("GEMINI_API_KEY")
_hf_token   = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

# ── LLM wale models bana lo ────────────────────────────────────────────────────

gc_model = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",        # guest collection ke liye fast model
    google_api_key=_gemini_key,
    temperature=1.0,
)

_insurance_model_base = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",  # best tool calling — user ne gemini-3.1-pro-preview suggest kiya tha, yeh latest preview use karo
    google_api_key=_gemini_key,
    temperature=0.2,
)

info_extractor = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",        # structured output ke liye
    google_api_key=_gemini_key,
    temperature=0,
).with_structured_output(GuestResponseExtract)

info_validator = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",        # structured output ke liye
    google_api_key=_gemini_key,
    temperature=0,
).with_structured_output(GuestResponseValidate)

# ── Embedding aur ML model ────────────────────────────────────────────────────

embedding_model = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=_hf_token,
)

ml_model = joblib.load("best_mode2.pk1")

# ── Support tools ─────────────────────────────────────────────────────────────
# Models pehle define hone chahiye, tab hi import karo — taaki tools
# embedding_model / ml_model ko agent.graph se safely back-import kar sakein bina circular errors ke.

from agent.tools.support.new_policy_inquiry import new_policy_inquiry
from agent.tools.support.get_specific_policy_details import get_specific_policy_details
from agent.tools.support.gives_validity_and_next_bill_info import gives_validity_and_next_bill_info
from agent.tools.support.get_faq_answer import get_faq_answer
from agent.tools.support.get_user_policies import get_user_policies
from agent.tools.support.get_premium_breakdown import get_premium_breakdown
from agent.tools.support.get_claim_history import get_claim_history
from agent.tools.support.compare_policies import compare_policies
from agent.tools.support.escalate_to_support import escalate_to_support

_support_tools = [
    new_policy_inquiry,
    get_specific_policy_details,
    compare_policies,
    get_user_policies,
    gives_validity_and_next_bill_info,
    get_premium_breakdown,
    get_claim_history,
    get_faq_answer,
    escalate_to_support,
]

# ── Purchase tools ─────────────────────────────────────────────────────────────

from agent.tools.purchase.initiate_purchase import initiate_purchase
from agent.tools.purchase.create_payment_order import create_payment_order
from agent.tools.purchase.confirm_purchase import confirm_purchase

_purchase_tools = [
    initiate_purchase,
    create_payment_order,
    confirm_purchase,
]

# ── Renewal aur Policy management tools ───────────────────────────────────────

from agent.tools.upgrade_and_renewal.get_renewal_summary import get_renewal_summary
from agent.tools.upgrade_and_renewal.create_renewal_payment import create_renewal_payment
from agent.tools.upgrade_and_renewal.confirm_renewal import confirm_renewal
from agent.tools.upgrade_and_renewal.get_upgrade_options import get_upgrade_options
from agent.tools.upgrade_and_renewal.initiate_upgrade import initiate_upgrade
from agent.tools.upgrade_and_renewal.create_upgrade_payment import create_upgrade_payment
from agent.tools.upgrade_and_renewal.confirm_upgrade import confirm_upgrade
from agent.tools.upgrade_and_renewal.cancel_policy import cancel_policy

_renewal_tools = [
    get_renewal_summary,
    create_renewal_payment,
    confirm_renewal,
    get_upgrade_options,
    initiate_upgrade,
    create_upgrade_payment,
    confirm_upgrade,
    cancel_policy,
]

# ── Claim tools ────────────────────────────────────────────────────────────────

from agent.tools.claim.initiate_claim import initiate_claim
from agent.tools.claim.assess_claim import assess_claim
from agent.tools.claim.approve_claim import approve_claim
from agent.tools.claim.flag_for_human_review import flag_for_human_review
from agent.tools.claim.escalate_claim_to_crm import escalate_claim_to_crm
from agent.tools.claim.check_claim_status import check_claim_status

_claim_tools = [
    initiate_claim,
    assess_claim,
    approve_claim,
    flag_for_human_review,
    escalate_claim_to_crm,
    check_claim_status,
]

# ── Tools ko models se jod do ──────────────────────────────────────────────────

# Har flow ka apna model — sirf apni flow ke tools bind hote hain
support_model   = _insurance_model_base.bind_tools(_support_tools)
purchase_model  = _insurance_model_base.bind_tools(_purchase_tools)
renewal_model   = _insurance_model_base.bind_tools(_renewal_tools)
claim_model     = _insurance_model_base.bind_tools(_claim_tools)

# Orchestrator ke models — koi tools nahi.
# router_model intent classify karta hai, general_model casual chat handle karta hai.
router_model    = _insurance_model_base.with_structured_output(RouteDecision)
general_model   = _insurance_model_base

# messages_key="text" — graph state mein messages "text" key ke neeche hain, "messages" nahi
tool_node          = ToolNode(_support_tools,   messages_key="text")
purchase_tool_node = ToolNode(_purchase_tools,  messages_key="text")
renewal_tool_node  = ToolNode(_renewal_tools,   messages_key="text")
claim_tool_node    = ToolNode(_claim_tools,     messages_key="text")

# ── Nodes ─────────────────────────────────────────────────────────────────────
# Saare models bind hone ke baad import karo — taaki har node ka sahi version mile.

from agent.nodes.guest_flow import (
    check_user,
    guest_flow,
    ask_name,
    ask_email,
    ask_number,
    ask_pincode,
    login_popup,
)
from agent.nodes.orchestrator import orchestrator
from agent.nodes.auth_flow import support_bot
from agent.nodes.purchase_flow import purchase_bot
from agent.nodes.renewal_flow import renewal_bot
from agent.nodes.claim_flow import claim_bot
from agent.nodes.condition import (
    route_by_auth,
    route_from_orchestrator,
    route_after_support_bot,
    route_after_purchase_bot,
    route_after_renewal_bot,
    route_after_claim_bot,
)

# ── Graph banao ───────────────────────────────────────────────────────────────

builder = StateGraph(OrchestrationState)

# Guest ko onboard karne ka sequence
builder.add_node("check_user",  check_user)
builder.add_node("guest_flow",  guest_flow)
builder.add_node("ask_name",    ask_name)
builder.add_node("ask_email",   ask_email)
builder.add_node("ask_number",  ask_number)
builder.add_node("ask_pincode", ask_pincode)
builder.add_node("login_popup", login_popup)

# Routing brain — har turn pe intent classify karke flow choose karti hai
builder.add_node("orchestrator", orchestrator)

# Support flow ka bot aur uske tools
builder.add_node("support_bot", support_bot)
builder.add_node("tools",       tool_node)

# Purchase flow ke nodes
builder.add_node("purchase_bot",   purchase_bot)
builder.add_node("purchase_tools", purchase_tool_node)

# Renewal aur policy management flow ke nodes
builder.add_node("renewal_bot",   renewal_bot)
builder.add_node("renewal_tools", renewal_tool_node)

# Claims flow ke nodes
builder.add_node("claim_bot",   claim_bot)
builder.add_node("claim_tools", claim_tool_node)

# ── Graph ke edges connect karo ────────────────────────────────────────────────

builder.add_edge(START, "check_user")

builder.add_conditional_edges(
    "check_user",
    route_by_auth,
    {"orchestrator": "orchestrator", "guest_flow": "guest_flow"},
)

# Guest onboarding ka sequence — har node mein Command(goto=...) se internal routing hoti hai
builder.add_edge("guest_flow", "ask_name")
builder.add_edge("login_popup", END)

# Orchestrator decide karti hai kaunsi flow handle karegi — yahi flow-jumping ka core hai
builder.add_conditional_edges(
    "orchestrator",
    route_from_orchestrator,
    {
        "support_bot":  "support_bot",
        "purchase_bot": "purchase_bot",
        "renewal_bot":  "renewal_bot",
        "claim_bot":    "claim_bot",
        END:            END,   # general chat — orchestrator khud reply kar chuki
    },
)

# Support flow ka chakkar — apne tools ke saath loop
builder.add_conditional_edges(
    "support_bot",
    route_after_support_bot,
    {"tools": "tools", END: END},
)
builder.add_edge("tools", "support_bot")

# Purchase flow ka chakkar
builder.add_conditional_edges(
    "purchase_bot",
    route_after_purchase_bot,
    {"purchase_tools": "purchase_tools", END: END},
)
builder.add_edge("purchase_tools", "purchase_bot")

# Renewal flow ka chakkar
builder.add_conditional_edges(
    "renewal_bot",
    route_after_renewal_bot,
    {"renewal_tools": "renewal_tools", END: END},
)
builder.add_edge("renewal_tools", "renewal_bot")

# Claims flow ka chakkar
builder.add_conditional_edges(
    "claim_bot",
    route_after_claim_bot,
    {"claim_tools": "claim_tools", END: END},
)
builder.add_edge("claim_tools", "claim_bot")

_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234567890-=@localhost:5432/insurance_database"
)

# Yeh sab startup() mein populate honge — import time pe event loop nahi hota
# isliye AsyncPostgresSaver ka constructor yahan nahi chal sakta.
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
app = None  # startup() ke baad compiled graph yahan milega


async def startup() -> None:
    """Pool kholo, checkpoint tables banao, graph compile karo. FastAPI lifespan se call hoti hai."""
    global _pool, _checkpointer, app
    _pool = AsyncConnectionPool(
        conninfo=_DB_URL,
        max_size=10,
        open=False,  # manually open karo — double-open se bachne ke liye
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    app = builder.compile(checkpointer=_checkpointer)


async def shutdown() -> None:
    """Connection pool gracefully band karo. FastAPI lifespan se call hoti hai."""
    if _pool is not None:
        await _pool.close()
