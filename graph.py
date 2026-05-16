from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage,SystemMessage,HumanMessage

from langgraph.graph import StateGraph,START,END
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
    temperature=1.0,
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

class ModelState(BaseModel):

    text: Annotated[List[BaseMessage],add_messages] = Field(default_factory=lambda:[])
    user_valid: bool = Field(default=False)
    user_info: Optional[User] = None
    session_id : str = Field(default_factory=lambda: str(uuid4())) #should have callable function
    auth_user_id : Optional[int] = Field(default=None)
    prompt : str = Field(default="")
    guest_info : Optional[GuestResponseExtract] = None

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


def merge_guest_info(
    old_info: Optional[GuestResponseExtract],
    new_info: GuestResponseExtract
):
    
    if old_info is None:
        return new_info

    updated_data = old_info.model_dump()

    for key, value in new_info.model_dump().items():
        if value is not None:
            updated_data[key] = value

    return GuestResponseExtract(**updated_data)


def ask_name(state:ModelState):

    res = gc_model.invoke([SystemMessage(content=state.prompt),*state.text])
    latest_human_message = ""

    for msg in reversed(state.text):
        if isinstance(msg, HumanMessage):
            latest_human_message = msg.content
            break
    
    output = info_extractor.invoke(latest_human_message)
    updated_guest_info = merge_guest_info(
    state.guest_info,
    output
    )
    return {"text":[res],"guest_info": updated_guest_info}
                
    

def ask_email(state:ModelState):

    state.prompt = """
        You are an insurance AI assistant, who have to sell insurance to the user, and user may inquiry u directly for insurance but before doing that
        Greet warmly and ask one by one for:
        name
        the user may still response will something else, but make sure to ensure him that i will come back to your query, can you help me with your email, then followed by other details,
        but dont ask name email phone number in a straight go, ask it sequentially while ensuring the user queries.
        after asking all of this ask the user what type of insuruance he/she wants.
        health insurance
        life insurance
        motor insurance
        """.strip()

    res = gc_model.invoke([SystemMessage(content=state.prompt),*state.text])
    latest_human_message = ""

    for msg in reversed(state.text):
        if isinstance(msg, HumanMessage):
            latest_human_message = msg.content
            break
    
    output = info_extractor.invoke(latest_human_message)
    updated_guest_info = merge_guest_info(
    state.guest_info,
    output
    )
    return {"text":[res],"guest_info": updated_guest_info}

def ask_number(state:ModelState):

    state.prompt = """
        You are an insurance AI assistant, who have to sell insurance to the user, and user may inquiry u directly for insurance but before doing that
        ask user for:
        phone number
        the user may still response will something else, but make sure to ensure him that i will come back to your query, can you help me with your phone number, then followed by other details,
        but dont ask name email phone number in a straight go, ask it sequentially while ensuring the user queries.
        after asking all of this ask the user what type of insuruance he/she wants.
        health insurance
        life insurance
        motor insurance
        """.strip()

    res = gc_model.invoke([SystemMessage(content=state.prompt),*state.text])
    latest_human_message = ""

    for msg in reversed(state.text):
        if isinstance(msg, HumanMessage):
            latest_human_message = msg.content
            break
    
    output = info_extractor.invoke(latest_human_message)
    updated_guest_info = merge_guest_info(
    state.guest_info,
    output
    )
    return {"text":[res],"guest_info": updated_guest_info}

def ask_pincode(state:ModelState):

    state.prompt = """
        You are an insurance AI assistant, who have to sell insurance to the user, and user may inquiry u directly for insurance but before doing that
        ask user for:
        pincode
        the user may still response will something else, but make sure to ensure him that i will come back to your query, can you help me with your pincode, then followed by other details,
        but dont ask name email phone number in a straight go, ask it sequentially while ensuring the user queries.
        after asking all of this ask the user what type of insuruance he/she wants.
        health insurance
        life insurance
        motor insurance
        """.strip()

    res = gc_model.invoke([SystemMessage(content=state.prompt),*state.text])
    latest_human_message = ""

    for msg in reversed(state.text):
        if isinstance(msg, HumanMessage):
            latest_human_message = msg.content
            break
    
    output = info_extractor.invoke(latest_human_message)
    updated_guest_info = merge_guest_info(
    state.guest_info,
    output
    )
    return {"text":[res],"guest_info": updated_guest_info}

def insurance_chat_node(state:ModelState):

    res = gc_model.invoke([SystemMessage(content=state.prompt),*state.text])
    return {'text':[res]}

def user_valid_or_not(state:ModelState):
    if state.user_valid:
        return 'insurance_chat_node'
    else:
        return 'ask_name'



def follow_step(state:ModelState):
    state = state.guest_info
    if state.name:
        if state.pincode:
            if state.email:
                if state.number:
                    return "human_in_the_loop"
                else:
                    return "ask_number"   
            else:
                return "ask_email"
        else:
            return "ask_pincode"
    else:
        return "ask_name"


          


    
    




