from pydantic import BaseModel
from typing import Optional, Dict, Any


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    city: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    # frontend uses this to decide whether to show questionnaire before chat
    risk_profile_completed: bool = False


class UserProfile(BaseModel):
    user_id: int
    name: str
    email: str
    city: Optional[str] = None
    is_active: bool
    risk_profile_completed: bool = False


class QuestionnaireSubmit(BaseModel):
    """30-MCQ answers — {question_key: chosen_value}."""
    answers: Dict[str, Any]


class QuestionnaireStatus(BaseModel):
    completed: bool
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None


class ProfileFull(BaseModel):
    """full user profile including all demographic fields used for ML risk scoring."""
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    income_category: Optional[str] = None
    occupation: Optional[str] = None
    smoker: Optional[bool] = None
    alcohol_consumption: Optional[str] = None
    bmi: Optional[float] = None
    exercise_frequency: Optional[str] = None
    chronic_disease: Optional[bool] = None
    claims_history: Optional[int] = None
    marital_status: Optional[str] = None
    dependents: Optional[int] = None
    vehicle_age: Optional[int] = None
    driving_violations: Optional[int] = None
    annual_mileage: Optional[int] = None


class ProfileUpdate(BaseModel):
    """all fields optional — only sent fields get updated."""
    name: Optional[str] = None
    city: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    income_category: Optional[str] = None
    occupation: Optional[str] = None
    smoker: Optional[bool] = None
    alcohol_consumption: Optional[str] = None
    bmi: Optional[float] = None
    exercise_frequency: Optional[str] = None
    chronic_disease: Optional[bool] = None
    claims_history: Optional[int] = None
    marital_status: Optional[str] = None
    dependents: Optional[int] = None
    vehicle_age: Optional[int] = None
    driving_violations: Optional[int] = None
    annual_mileage: Optional[int] = None
