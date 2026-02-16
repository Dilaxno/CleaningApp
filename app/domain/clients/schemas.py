"""Client domain schemas - Pydantic models for validation"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from ...shared.validators import validate_us_phone


class ClientCreate(BaseModel):
    """Schema for creating a new client"""

    businessName: str
    contactName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    propertyType: Optional[str] = None
    propertySize: Optional[int] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""

    businessName: Optional[str] = None
    contactName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    propertyType: Optional[str] = None
    propertySize: Optional[int] = None
    frequency: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class ClientResponse(BaseModel):
    """Schema for client response"""

    id: int
    public_id: Optional[str] = None
    businessName: str
    contactName: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    propertyType: Optional[str]
    propertySize: Optional[int]
    frequency: Optional[str]
    status: str
    notes: Optional[str]
    created_at: Optional[datetime] = None
    form_data: Optional[dict] = None

    class Config:
        from_attributes = True


class PublicClientCreate(BaseModel):
    """Schema for public form submission"""

    ownerUid: str
    templateId: str
    businessName: str
    contactName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    propertyType: Optional[str] = None
    propertySize: Optional[int] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None
    formData: Optional[dict] = None
    clientSignature: Optional[str] = None
    quoteAccepted: Optional[bool] = False
    quoteStatus: Optional[str] = None
    createOnly: Optional[bool] = False

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class BatchDeleteRequest(BaseModel):
    """Schema for batch delete operation"""

    clientIds: list[int]


class BatchDeleteQuoteRequestsRequest(BaseModel):
    """Schema for batch delete quote requests"""

    quoteRequestIds: list[int]


class QuotePreviewRequest(BaseModel):
    """Schema for quote preview calculation"""

    ownerUid: str
    formData: dict


class QuoteAdjustmentRequest(BaseModel):
    """Schema for adjusting a quote"""

    adjusted_amount: float
    adjustment_notes: str

    @field_validator("adjusted_amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Adjusted amount must be greater than 0")
        return v
