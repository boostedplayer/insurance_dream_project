from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from pydantic import BaseModel,Field
from typing import List,Optional,Annotated
from uuid import uuid4
from agent.state.user import GuestResponseExtract
from agent.state.user import User

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
    
