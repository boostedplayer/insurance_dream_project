from sqlalchemy import text
from langchain_core.messages import AIMessage,SystemMessage,HumanMessage
from langgraph.types import Command

from agent.prompts.validation_prompt import validation_prompt
from agent.graph import gc_model,info_validator,info_extractor
from agent.state.orchestration_state import OrchestrationState
from agent.state.user import User
from agent.db.db import engine


def check_user(state:OrchestrationState):

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
    

def guest_flow(state:OrchestrationState):
    msg = AIMessage(content="Hi, welcome to our insurance assistant. can i get your name please?")
    return {'text':[msg]}



def ask_name(state:OrchestrationState):

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
      
    

def ask_email(state:OrchestrationState):

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
    


def ask_number(state:OrchestrationState):

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




def ask_pincode(state:OrchestrationState):
    
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

def login_popup(state:OrchestrationState):
    """ 
    will be done by django
    """