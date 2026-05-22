from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage,SystemMessage,HumanMessage,AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool 
from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph,START,END
from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from pydantic import BaseModel,Field,EmailStr
from typing import Annotated,List,Dict,Optional,Any

import pandas as pd
from uuid import uuid4
from db import engine
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

class User(BaseModel):

    user_id: Optional[int] = None
    policy_id: Optional[int] = None

    name: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = None
    email: Optional[EmailStr] = None

    user_behaviour: Optional[str] = None
    is_active: bool = True
    claims: Optional[int] = 0


class GuestResponseExtract(BaseModel):

    name: Optional[str] = Field(default=None, max_length=50,description="extract the user name from the text")
    pincode: Optional[str] = Field(default=None, max_length=10,description="extract the user's location pincode from the text")
    email: Optional[EmailStr] = Field(default=None,description="extract the user's email from the text")
    number: Optional[str] = Field(default=None, max_length=15,description="extract the user's phone number from the text")
  
info_extractor = info_extractor.with_structured_output(GuestResponseExtract)

class ValidatorModel(BaseModel):

    model_ques: str = ""
    user_ans: str = ""

class GuestResponseValidate(BaseModel):

    is_valid : bool = Field(default = False, description="validate whether the user's answer is according to model's question, if it is according to model's question return true else false")

info_validator = info_validator.with_structured_output(GuestResponseValidate)

validation_prompt = PromptTemplate.from_template("""
You are a strict validation system.

Your job is to determine whether the user's answer correctly answers the assistant's question.

Assistant Question:
{model_ques}

User Answer:
{user_ans}

Validation Rules:

- Return TRUE only if the user clearly provided the requested information.
- Return FALSE if:
    - the answer is unrelated
    - the user changed topic
    - the information is incomplete
    - the information format is invalid
    - the user avoided answering
    - the answer is conversational only

Field-specific validation:

- Name:
    valid example:
        "my name is rahul"
        "rahul"
    invalid:
        "why do you need it?"

- Email:
    valid only if it contains a real email format like:
        example@gmail.com
    invalid:
        "hello"
        "my mail"
        "gmail only"

- Phone Number:
    valid only if it contains a realistic phone number.
    invalid:
        "call me maybe"
        "123"

- Pincode:
    valid only if it contains a valid numeric pincode.
    invalid:
        "delhi"
        "near airport"

Return whether the answer is valid.
""")

class ModelState(BaseModel):

    text: Annotated[List[BaseMessage],add_messages] = Field(default_factory=lambda:[])
    user_valid: bool = Field(default=False)
    user_info: Optional[User] = None
    session_id : str = Field(default_factory=lambda: str(uuid4())) #should have callable function
    auth_user_id : Optional[int] = Field(default=None)
    prompt : str = Field(default="")
    guest_info : GuestResponseExtract = Field(
    default_factory=GuestResponseExtract
)


# will check whether the user exits in db or not
#checking from db that user is valid.


def check_user(state:ModelState):

    with engine.connect() as conn:
       data = conn.execute(
            text("""
        SELECT * FROM users 
        WHERE user_id = :user_id
            """),
        {"user_id":state.auth_user_id}
        )
       
       data = data.fetchone()

    if data:
        user_dict =dict(data._mapping)
        return {'user_valid':True, 'user_info':User(**user_dict)} #to avoid mutating
    else:
        return {"user_valid":False}
    

def guest_flow(state:ModelState):
    msg = AIMessage(content="Hi, welcome to our insurance assistant. can i get your name please?")
    return {'text':[msg]}


def route_by_auth(state:ModelState):
    if state.user_valid:
        return "insurance_bot"
    else:
        return "guest_flow"


def ask_name(state:ModelState):

    latest_human_message = ""
    latest_model_message = ""

    for msg in reversed(state.text):

        if not latest_human_message and isinstance(msg, HumanMessage):
            latest_human_message = msg.content

        if not latest_model_message and isinstance(msg, AIMessage):
            latest_model_message = msg.content

        if latest_human_message and latest_model_message:
            break

    output = info_extractor.invoke(latest_human_message)
    text = validation_prompt.format(
        model_ques = latest_model_message,
        user_ans = latest_human_message
    )
    valid = info_validator.invoke(text)
    if valid.is_valid:
        update = state.guest_info.model_copy(
            update = {
                "name":output.name
        })
        res = gc_model.invoke([SystemMessage(content=f"appreciate user for telling the name, use the provided name to personalize the chats and ask the user politely to provide the email. "),*state.text])
        return Command(
            update = {"text":[res],"guest_info":update},
            goto = "ask_email"
        )
    
    res = gc_model.invoke([SystemMessage(content="user didnt gave u his/her name, appreciate his last concern, tell him politely that you will get back to that concern after getting details, again ask user politey for his name"),*state.text])
    return Command(
        update = {'text':[res]},
        goto = "ask_name"
    )


                
    

def ask_email(state:ModelState):

    latest_human_message = ""
    latest_model_message = ""

    for msg in reversed(state.text):

        if not latest_human_message and isinstance(msg, HumanMessage):
            latest_human_message = msg.content

        if not latest_model_message and isinstance(msg, AIMessage):
            latest_model_message = msg.content

        if latest_human_message and latest_model_message:
            break
    
    output = info_extractor.invoke(latest_human_message)
    text = validation_prompt.format(
        model_ques = latest_model_message,
        user_ans = latest_human_message
    )
    valid = info_validator.invoke(text)
    if valid.is_valid:
        update = state.guest_info.model_copy(
            update = {
                "email":output.email
            }
        )
        res = gc_model.invoke([SystemMessage(content="appreciate user for telling the email, ask the user politely to provide the number. "),*state.text])
        return Command(
            update = {'text':[res],'guest_info':update},
            goto = "ask_number"
        )
    res = gc_model.invoke([SystemMessage(content="user didnt gave u his/her email, appreciate his last concern if he had any, tell him politely that you will get back to that concern after getting details, again ask user politey for his email"),*state.text])
    return Command(
        update={'text':[res]},
        goto = "ask_email"
    )
    


def ask_number(state:ModelState):

    latest_human_message = ""
    latest_model_message = ""

    for msg in reversed(state.text):

        if not latest_human_message and isinstance(msg, HumanMessage):
            latest_human_message = msg.content

        if not latest_model_message and isinstance(msg, AIMessage):
            latest_model_message = msg.content

        if latest_human_message and latest_model_message:
            break
    
    output = info_extractor.invoke(latest_human_message)
    text = validation_prompt.format(
        model_ques = latest_model_message,
        user_ans = latest_human_message
    )
    valid = info_validator.invoke(text)
    if valid.is_valid:
        update = state.guest_info.model_copy(
            update = {
                "number":output.number
        })
        res = gc_model.invoke([SystemMessage(content="appreciate user for telling the number, ask the user politely to provide the pincode."),*state.text])
        return Command(
            update = {'text':[res],'guest_info':update},
            goto = 'ask_pincode'
        )
    
    res = gc_model.invoke([SystemMessage(content="user didnt gave u his/her number, appreciate his last concern if he had any, tell him politely that you will get back to that concern after getting details, again ask user politey for his number"),*state.text])
    return Command(
        update = {'text':[res]},
        goto = 'ask_number'
    )




def ask_pincode(state:ModelState):
    
    latest_human_message = ""
    latest_model_message = ""

    for msg in reversed(state.text):

        if not latest_human_message and isinstance(msg, HumanMessage):
            latest_human_message = msg.content

        if not latest_model_message and isinstance(msg, AIMessage):
            latest_model_message = msg.content

        if latest_human_message and latest_model_message:
            break
    
    output = info_extractor.invoke(latest_human_message)
    text = validation_prompt.format(
        model_ques = latest_model_message,
        user_ans = latest_human_message
    )
    valid = info_validator.invoke(text)
    if valid.is_valid:
        updated = state.guest_info.model_copy(
            update = {
                "pincode":output.pincode
            }
        )
        res = gc_model.invoke([SystemMessage(content="appreciate user for telling the pincode, ask the user politely to login to further proceed or wait for agent to contact you through the given details."),*state.text])
        return Command(
            update ={"text":[res],"guest_info": updated},
            goto = 'login_popup'
        )
    
    res = gc_model.invoke([SystemMessage(content="user didnt gave u his/her pincode, appreciate his last concern if he had any, tell him politely that you will get back to that concern after getting details, again ask user politey for his pincode"),*state.text])
    return Command(
            update ={"text":[res]},
            goto = 'ask_pincode'
        )

def login_popup(state:ModelState):
    """ 
    will be done by django
    """

insurance_prompt ="""
You are an insurance AI assistant for authenticated users.
Your job is to help the user with insurance-related tasks such as:
- answering questions about an existing policy
- explaining coverage and exclusions
- helping with new policy inquiries
- helping the user buy a policy
- helping upgrade an existing policy
- helping renew an existing policy
- helping initiate or understand an insurance claim

Behavior rules:
- Greet the user warmly and professionally.
- Understand the user's intent from natural language.
- If the request is ambiguous, ask one short clarifying question before proceeding.
- If the user refers to "this policy", "my insurance", or "that plan", identify which policy they mean before answering.
- Be concise, clear, and helpful.
- Never invent policy details, claim eligibility, coverage, renewal status, premium amount, grace period, or benefits.
- Use available tools or backend functions whenever policy-specific, claim-specific, renewal-specific, or user-specific information is needed.
- If a tool returns missing, incomplete, or conflicting data, explain that clearly and ask the user for the minimum additional information needed.
- If the user asks about coverage, clearly separate:
  1. what is covered,
  2. what may not be covered,
  3. what depends on policy terms or approval.
- If the user wants to buy insurance, first identify the insurance type they want, such as health, life, or motor insurance.
- If the user wants to renew insurance, check eligibility and grace-period status before saying renewal is possible.
- If the user wants to upgrade insurance, first identify their current policy and then check upgrade options.
- If the user wants to make a claim, first identify the policy, claim type, and essential details needed to proceed.
- If the user asks for premium-related information, provide estimates only when supported by available logic or tools, and clearly label them as estimates when they are not final.
- If the request is outside insurance support scope, politely say so and guide the user back to insurance-related help.

Tool usage rules:
- Use the appropriate tool or function whenever the answer depends on user-specific policy data.
- Do not rely only on conversational assumptions for existing policy details.
- Prefer tool-based verification over guessing.
- After receiving tool output, explain the result in simple language.

Response style:
- Sound like a professional insurance support assistant.
- Use plain English.
- Avoid unnecessary jargon.
- Keep answers structured and action-oriented.
- When needed, give the user the next best step.

Your goal is to help the user complete the insurance task with the fewest necessary follow-up questions.
""".strip()

tools = [new_policy_inquiry,existing_policy_query,coverage_check,buy_insurance,upgrade_insurance,renew_insurance,claim_insurance] 
insurance_model = insurance_model.bind_tools(tools)
tool_node = ToolNode(tools)

def insurance_bot(state:ModelState):

    res = insurance_model.invoke([SystemMessage(content=insurance_prompt ),*state.text])
    return {"text":[res]}
 

def get_risk_category(score):

    if score >= 90:
        return "very_high"

    elif score >= 80:
        return "high"

    elif score >= 70:
        return "upper_middle"

    elif score >= 60:
        return "middle"

    elif score >= 50:
        return "lower_middle"

    elif score >= 25:
        return "low"

    return "very_low"

RISK_LOADING = {
"very_low": 0.00,
"low": 0.05,
"lower_middle": 0.10,
"middle": 0.15,
"upper_middle": 0.25,
"high": 0.40,
"very_high": 0.60
}

@tool
def new_policy_inquiry(policy_type : str, config : RunnableConfig) -> List[dict[str,Any]]:
    """
    Use when the user wants to inquire about a new insurance policy.

    policy_type should be one of:
    - health
    - motor
    - life

    Returns the top 3 policy suggestions for that insurance type.
    """
    auth_user_id = config["configurable"]["auth_user_id"]
    if policy_type not in {"health", "motor", "life"}:
        return [{
            "error":"Invalid policy_type. Use: health, motor, or life."
        }]
    
    with engine.connect() as conn:

        data = conn.execute(text("""
        SELECT age,gender,income_category,occupation,smoker,alcohol_consumption,bmi,exercise_frequency,chronic_disease,claims_history,marital_status,dependents,vehicle_age,driving_violations, annual_mileage,city FROM users where user_id = :user_id
        """),{'user_id':auth_user_id})
        data = data.fetchone()
    
    if data is None:
        return [{
            "error":"user not found"
        }]
      
    user_df = pd.DataFrame([dict(data._mapping)])

    risk_score = ml_model.predict(user_df)[0]
    risk_category = get_risk_category(risk_score)


    with engine.connect() as conn:

        policies = conn.execute(text("""
        SELECT * FROM policy where policy_category = :risk_category and policy_type = :policy_type LIMIT 3
        """),{'risk_category':risk_category,'policy_type':policy_type})
        policies = policies.fetchall()
    
    if not policies:
        return [{
            "message": f"No {policy_type} policies found for {risk_category} risk category"
        }]

    loading_percent = RISK_LOADING[risk_category]

    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO underwriting_results (
                user_id,
                risk_score,
                risk_category,
                loading_percent
            )
            VALUES (
                :user_id,
                :risk_score,
                :risk_category,
                :loading_percent
            ) 
            """),
            {
                "user_id" : auth_user_id,
                "risk_score" : risk_score,
                "risk_category" : risk_category,
                "loading_percent": loading_percent,
                
            }
        )
        # as user havent bought right know so we dont put any details of policy yet and amount yet.
        # im giving 3 best policy in that category and their premium is different
        # so when user will select a one, im gonna put that details only then

    return {
        "user_risk_profile": {
            "risk_category": risk_category,
        },

        "recommended_policies": [
            {
                "policy_name": i.policy_name,
                "policy_id": i.policy_id,
                "base_premium": i.premium,
                "risk_loading_percent": loading_percent,
                "final_premium": round(i.premium+i.premium*loading_percent,2),
                "coverage_amount": i.coverage_amount,
                "covers": i.covers,
            }
            for i in policies
        ]
    }
    


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








          


    
    




