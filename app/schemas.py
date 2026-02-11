from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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


# Custom Quote Request Schemas
class CustomQuoteRequestCreate(BaseModel):
    client_id: int
    video_filename: str
    video_size_bytes: int
    video_duration_seconds: Optional[float] = None
    video_mime_type: str
    client_ip: Optional[str] = None
    client_user_agent: Optional[str] = None


class CustomQuoteLineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    total: float


class CustomQuoteSubmission(BaseModel):
    custom_quote_amount: float
    custom_quote_description: Optional[str] = None
    custom_quote_line_items: Optional[List[CustomQuoteLineItem]] = None
    custom_quote_notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class CustomQuoteApproval(BaseModel):
    client_response: str = Field(..., pattern="^(approved|rejected)$")
    client_response_notes: Optional[str] = None


class CustomQuoteRequestResponse(BaseModel):
    id: int
    public_id: str
    user_id: int
    client_id: int
    video_filename: str
    video_size_bytes: int
    video_duration_seconds: Optional[float]
    video_mime_type: str
    status: str
    custom_quote_amount: Optional[float]
    custom_quote_currency: str
    custom_quote_description: Optional[str]
    custom_quote_line_items: Optional[List[Dict[str, Any]]]
    custom_quote_notes: Optional[str]
    quoted_at: Optional[datetime]
    client_response: Optional[str]
    client_response_notes: Optional[str]
    responded_at: Optional[datetime]
    contract_id: Optional[int]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Include client details
    client: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class VideoUploadUrlResponse(BaseModel):
    upload_url: str
    r2_key: str
    expires_in: int = 3600  # 1 hour
