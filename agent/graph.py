from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage,SystemMessage,HumanMessage,AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool 
from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph,START,END
from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent.state.user import GuestResponseExtract,GuestResponseValidate,User
from agent.state.model_state import ModelState
from agent.prompts.validation_prompt import validation_prompt
from agent.prompts.insurance_prompt import insurance_prompt

import pandas as pd
from uuid import uuid4
from agent.db.db import engine
from sqlalchemy import text
from dotenv import load_dotenv
import os
import joblib


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

gc_model = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key=api_key,
    temperature=1.0,
)

insurance_model = ChatGroq(
    model = "openai/gpt-120b-oss",
    temperature=0.2,
    api_key=api_key,
)

info_extractor = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key=api_key,
    temperature=0,
)

info_validator = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key = api_key,
    temperature=0,
)

ml_model = joblib.load('best_mode2.pk1')
  
info_extractor = info_extractor.with_structured_output(GuestResponseExtract)

info_validator = info_validator.with_structured_output(GuestResponseValidate)




#tools = [new_policy_inquiry,existing_policy_query,coverage_check,buy_insurance,upgrade_insurance,renew_insurance,claim_insurance] 
# insurance_model = insurance_model.bind_tools(tools)
# tool_node = ToolNode(tools)

# @tool
# def existing_policy_query(state:ModelState):
# @tool
# def coverage_check(state:ModelState):
# @tool
# def buy_insurance(state:ModelState):
# @tool
# def upgrade_insurance(state:ModelState):
# @tool
# def renew_insurance(state:ModelState):
# @tool
# def claim_insurance(state:ModelState):








          


    
    




