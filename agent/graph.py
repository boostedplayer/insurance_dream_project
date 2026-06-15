from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from agent.state.orchestration_state import OrchestrationState
from agent.state.user import GuestResponseExtract, GuestResponseValidate, RouteDecision
from agent.prompts.insurance_prompt import insurance_prompt  # re-exported for nodes

import joblib
import os
from dotenv import load_dotenv

load_dotenv()

_gemini_key = os.getenv("GEMINI_API_KEY")
_hf_token   = os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")

# models

gc_model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",        # fast model for guest collection
    google_api_key=_gemini_key,
    temperature=1.0,
)

_insurance_model_base = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",  # best tool calling — was suggested gemini-3.1-pro-preview but this is the latest preview
    google_api_key=_gemini_key,
    temperature=0.2,
)

info_extractor = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",        # structured output
    google_api_key=_gemini_key,
    temperature=0,
).with_structured_output(GuestResponseExtract)

info_validator = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",        # structured output
    google_api_key=_gemini_key,
    temperature=0,
).with_structured_output(GuestResponseValidate)

# embedding + ML model

embedding_model = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=_hf_token,
)

ml_model = joblib.load("best_mode2.pk1")

# support tools — late import so tools can back-import embedding_model/ml_model from agent.graph without circular deps

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

# purchase tools

from agent.tools.purchase.initiate_purchase import initiate_purchase
from agent.tools.purchase.create_payment_order import create_payment_order
from agent.tools.purchase.confirm_purchase import confirm_purchase

_purchase_tools = [
    initiate_purchase,
    create_payment_order,
    confirm_purchase,
]

# renewal + policy management tools

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

# claim tools

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
    escalate_to_support,
]

# bind tools — each flow gets its own model with only its tools
support_model   = _insurance_model_base.bind_tools(_support_tools)
purchase_model  = _insurance_model_base.bind_tools(_purchase_tools)
renewal_model   = _insurance_model_base.bind_tools(_renewal_tools)
claim_model     = _insurance_model_base.bind_tools(_claim_tools)

# orchestrator models — no tools; router classifies intent, general handles casual chat
router_model    = _insurance_model_base.with_structured_output(RouteDecision)
general_model   = _insurance_model_base

# state uses "text" not "messages" as the key
tool_node          = ToolNode(_support_tools,   messages_key="text")
purchase_tool_node = ToolNode(_purchase_tools,  messages_key="text")
renewal_tool_node  = ToolNode(_renewal_tools,   messages_key="text")
claim_tool_node    = ToolNode(_claim_tools,     messages_key="text")

# nodes — import after all models are bound so each node gets the right version

from agent.nodes.guest_flow import (
    check_user,
    guest_flow,
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

# build graph

builder = StateGraph(OrchestrationState)

# guest onboarding — guest_flow is a turn-based stage machine, routes itself via Command(goto)
builder.add_node("check_user",  check_user)
builder.add_node("guest_flow",  guest_flow)
builder.add_node("login_popup", login_popup)

# classifies intent each turn and picks a flow
builder.add_node("orchestrator", orchestrator)

# support flow
builder.add_node("support_bot", support_bot)
builder.add_node("tools",       tool_node)

# purchase flow
builder.add_node("purchase_bot",   purchase_bot)
builder.add_node("purchase_tools", purchase_tool_node)

# renewal flow
builder.add_node("renewal_bot",   renewal_bot)
builder.add_node("renewal_tools", renewal_tool_node)

# claims flow
builder.add_node("claim_bot",   claim_bot)
builder.add_node("claim_tools", claim_tool_node)

# edges

builder.add_edge(START, "check_user")

builder.add_conditional_edges(
    "check_user",
    route_by_auth,
    {"orchestrator": "orchestrator", "guest_flow": "guest_flow"},
)

# guest_flow collects one detail per turn, routes to END or login_popup when done
builder.add_edge("login_popup", END)

# core flow-jumping logic lives here
builder.add_conditional_edges(
    "orchestrator",
    route_from_orchestrator,
    {
        "support_bot":  "support_bot",
        "purchase_bot": "purchase_bot",
        "renewal_bot":  "renewal_bot",
        "claim_bot":    "claim_bot",
        END:            END,   # general chat — orchestrator already replied
    },
)

# support loop
builder.add_conditional_edges(
    "support_bot",
    route_after_support_bot,
    {"tools": "tools", END: END},
)
builder.add_edge("tools", "support_bot")

# purchase loop
builder.add_conditional_edges(
    "purchase_bot",
    route_after_purchase_bot,
    {"purchase_tools": "purchase_tools", END: END},
)
builder.add_edge("purchase_tools", "purchase_bot")

# renewal loop
builder.add_conditional_edges(
    "renewal_bot",
    route_after_renewal_bot,
    {"renewal_tools": "renewal_tools", END: END},
)
builder.add_edge("renewal_tools", "renewal_bot")

# claims loop
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

# populated in startup() — no event loop at import time so can't construct AsyncPostgresSaver here
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
app = None  # compiled graph, set by startup()


async def startup() -> None:
    """open pool, setup checkpoint tables, compile graph. called from FastAPI lifespan."""
    global _pool, _checkpointer, app
    _pool = AsyncConnectionPool(
        conninfo=_DB_URL,
        max_size=10,
        open=False,  # open manually to avoid double-open
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    app = builder.compile(checkpointer=_checkpointer)


async def shutdown() -> None:
    """close pool on shutdown. called from FastAPI lifespan."""
    if _pool is not None:
        await _pool.close()
