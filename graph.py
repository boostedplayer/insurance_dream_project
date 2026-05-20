from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage,SystemMessage,HumanMessage,AIMessage
from langchain_core.prompts import PromptTemplate

from langgraph.graph import StateGraph,START,END
from langgraph.types import Command
from langgraph.graph.message import add_messages

from pydantic import BaseModel,Field,EmailStr
from typing import Annotated,List,Dict,Optional


from uuid import uuid4
from db import engine
from sqlalchemy import text
from dotenv import load_dotenv
import os


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

gc_model = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key=api_key,
    temperature=1.0,
)

info_extractor = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key=api_key,
    temperature=0.1,
)

info_validator = ChatGroq(
    model = "openai/gpt-120b-oss",
    api_key = api_key,
    temperature=0.1,
)


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

Return ONLY:
true
or
false
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
    
def prompt_generation(state:ModelState):

    if state.user_valid:

        user = state.user_info

        prompt = f"""
        You are an insurance AI assistant.
        here are the user all detials that u need {user.model_dump()},   
        Greet warmly and personalize the response.
        as well as ask the user about the queries if he or she facing any queries.
        
        """.strip()

    else:

        prompt = """
        You are an insurance AI assistant, who have to sell insurance to the user, and user may inquiry u directly for insurance but before doing that
        Greet warmly and ask one by one for:
        name
        the user may still response will something else, but make sure to ensure him that i will come back to your query, can you help me with your name, then followed by other details,
        but dont ask name email phone number in a straight go, ask it sequentially while ensuring the user queries.
        after asking all of this ask the user what type of insuruance he/she wants.
        health insurance
        life insurance
        motor insurance
        """.strip()

    return {"prompt":prompt}

def guest_flow(state:ModelState):
    msg = AIMessage(content="Hi, welcome to our insurance assistant. can i get your name please?")
    return {'text':[msg]}

def logged_flow(state:ModelState):
    msg = AIMessage(content="Hi, welcome to our insurance assistant. I’m here to help you with claims, renewals, or buying a policy.")
    return {'text':[msg]}

def route_by_auth(state:ModelState):
    if state.user_valid:
        return "logged_flow"
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
        res = gc_model.invoke([SystemMessage(content=f"appreciate user for telling the name, use user name to personalize the response, user name : {state.guest_info.name}, ask the user politely to provide the email. "),*state.text])
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
            goto = 'human_in_the_loop'
        )
    
    res = gc_model.invoke([SystemMessage(content="user didnt gave u his/her pincode, appreciate his last concern if he had any, tell him politely that you will get back to that concern after getting details, again ask user politey for his pincode"),*state.text])
    return Command(
            update ={"text":[res]},
            goto = 'ask_pincode'
        )




          


    
    




