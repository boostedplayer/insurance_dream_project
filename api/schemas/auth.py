from pydantic import BaseModel
from typing import Optional


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


class UserProfile(BaseModel):
    user_id: int
    name: str
    email: str
    city: Optional[str] = None
    is_active: bool


class ProfileFull(BaseModel):
    """Poora user profile — ML risk scoring ke saare demographic fields ke saath."""
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
    """Profile update — saare fields optional, jo bheje wahi update honge."""
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
