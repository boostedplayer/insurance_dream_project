from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None   # if None, backend creates one


class ChatResponse(BaseModel):
    response: str
    session_id: str
    current_flow: Optional[str] = None
    # true when guest has given all details and login popup should show
    show_login: Optional[bool] = None
