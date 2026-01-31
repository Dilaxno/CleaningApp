from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    account_type: Optional[str] = None
    hear_about: Optional[str] = None
    default_brand_color: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    firebase_uid: str
    full_name: Optional[str]
    email: str
    account_type: Optional[str]
    hear_about: Optional[str]
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str
