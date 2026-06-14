from pydantic import BaseModel,Field,EmailStr
from typing import List,Optional,Annotated,Literal
from uuid import uuid4


class RouteDecision(BaseModel):
    """Orchestrator ka routing decision — user ki intent kaunsi flow ko jaani chahiye."""
    flow: Literal["support", "purchase", "renewal", "claim", "general"] = Field(
        description="The single best-matching flow for the user's latest message"
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
  

class GuestResponseValidate(BaseModel):

    is_valid : bool = Field(default = False, description="validate whether the user's answer is according to model's question, if it is according to model's question return true else false")
