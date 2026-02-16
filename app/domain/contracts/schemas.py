"""Contract domain schemas - Pydantic models for validation"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContractCreate(BaseModel):
    """Schema for creating a new contract"""

    clientId: int
    title: str
    description: Optional[str] = None
    contractType: Optional[str] = None
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    totalValue: Optional[float] = None
    paymentTerms: Optional[str] = None
    termsConditions: Optional[str] = None


class ContractUpdate(BaseModel):
    """Schema for updating an existing contract"""

    title: Optional[str] = None
    description: Optional[str] = None
    contractType: Optional[str] = None
    status: Optional[str] = None
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    totalValue: Optional[float] = None
    paymentTerms: Optional[str] = None
    termsConditions: Optional[str] = None


class ContractResponse(BaseModel):
    """Schema for contract response"""

    id: int
    public_id: Optional[str] = None
    clientId: int
    clientPublicId: Optional[str] = None
    clientName: str
    clientEmail: Optional[str]
    title: str
    description: Optional[str]
    contractType: Optional[str]
    status: str
    startDate: Optional[datetime]
    endDate: Optional[datetime]
    totalValue: Optional[float]
    paymentTerms: Optional[str]
    termsConditions: Optional[str]
    pdfUrl: Optional[str]
    hasPdf: bool
    providerSignature: Optional[str]
    signedAt: Optional[datetime]
    clientSignatureTimestamp: Optional[datetime]
    providerSignedAt: Optional[datetime]
    createdAt: datetime
    defaultSignatureUrl: Optional[str] = None

    class Config:
        from_attributes = True


class ProviderSignatureRequest(BaseModel):
    """Schema for provider signature submission"""

    signature_data: str  # Base64 signature image
    use_default_signature: bool = False


class BatchDeleteRequest(BaseModel):
    """Schema for batch delete operation"""

    contract_ids: list[int]


class ContractGenerateRequest(BaseModel):
    """Schema for PDF generation request"""

    clientId: int
    ownerUid: str


class RevisionRequest(BaseModel):
    """Schema for contract revision request"""

    revision_type: str  # 'pricing', 'scope', 'both'
    revision_notes: str


class RevisionResponse(BaseModel):
    """Schema for revision response"""

    id: int
    revision_requested: bool
    revision_type: Optional[str] = None
    revision_notes: Optional[str] = None
    revision_requested_at: Optional[datetime] = None

    class Config:
        from_attributes = True
