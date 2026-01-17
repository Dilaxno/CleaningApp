import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models import User, Client, Contract, BusinessConfig
from ..auth import get_current_user
from .upload import generate_presigned_url
from ..email_service import send_contract_fully_executed_email, send_provider_contract_signed_confirmation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contracts"])


def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class ContractCreate(BaseModel):
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
    id: int
    public_id: Optional[str] = None  # UUID for public access (nullable for existing records)
    clientId: int
    clientPublicId: Optional[str] = None  # Client's UUID for public access (nullable for existing records)
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
    providerSignature: Optional[str]  # Base64 signature image
    signedAt: Optional[datetime]
    clientSignatureTimestamp: Optional[datetime]
    createdAt: datetime
    defaultSignatureUrl: Optional[str] = None  # Provider's default signature from onboarding

    class Config:
        from_attributes = True


class ProviderSignatureRequest(BaseModel):
    signature_data: str  # Base64 signature image
    use_default_signature: bool = False  # If true, use provider's default signature from onboarding


def get_pdf_url(pdf_key: Optional[str]) -> Optional[str]:
    """Generate presigned URL for PDF if key exists"""
    if not pdf_key:
        return None
    try:
        return generate_presigned_url(pdf_key, expiration=3600)
    except Exception:
        return None


@router.get("", response_model=List[ContractResponse])
async def get_contracts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all contracts for the current user"""
    contracts = db.query(Contract).filter(Contract.user_id == current_user.id).order_by(Contract.created_at.desc()).all()
    
    # Get provider's default signature from business config
    business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    default_signature_url = None
    if business_config and business_config.signature_url:
        try:
            default_signature_url = generate_presigned_url(business_config.signature_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for default signature: {e}")
    
    result = []
    for c in contracts:
        client = db.query(Client).filter(Client.id == c.client_id).first()
        pdf_url = get_pdf_url(c.pdf_key)
        result.append(ContractResponse(
            id=c.id,
            public_id=c.public_id,
            clientId=c.client_id,
            clientPublicId=client.public_id if client else None,
            clientName=client.business_name if client else "Unknown",
            clientEmail=client.email if client else None,
            title=c.title,
            description=c.description,
            contractType=c.contract_type,
            status=c.status,
            startDate=c.start_date,
            endDate=c.end_date,
            totalValue=c.total_value,
            paymentTerms=c.payment_terms,
            termsConditions=c.terms_conditions,
            pdfUrl=pdf_url,
            hasPdf=bool(c.pdf_key),
            providerSignature=c.provider_signature,
            signedAt=c.signed_at,
            clientSignatureTimestamp=c.client_signature_timestamp,
            createdAt=c.created_at,
            defaultSignatureUrl=default_signature_url
        ))
    return result


@router.post("", response_model=ContractResponse)
async def create_contract(
    data: ContractCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new contract"""
    logger.info(f"📥 Creating contract for user_id: {current_user.id}")
    
    # Verify client belongs to user
    client = db.query(Client).filter(Client.id == data.clientId, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    contract = Contract(
        user_id=current_user.id,
        client_id=data.clientId,
        title=data.title,
        description=data.description,
        contract_type=data.contractType,
        start_date=data.startDate,
        end_date=data.endDate,
        total_value=data.totalValue,
        payment_terms=data.paymentTerms,
        terms_conditions=data.termsConditions,
        status="new"
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    
    logger.info(f"✅ Contract created: id={contract.id}")
    return ContractResponse(
        id=contract.id,
        public_id=contract.public_id,
        clientId=contract.client_id,
        clientPublicId=client.public_id,
        clientName=client.business_name,
        clientEmail=client.email,
        title=contract.title,
        description=contract.description,
        contractType=contract.contract_type,
        status=contract.status,
        startDate=contract.start_date,
        endDate=contract.end_date,
        totalValue=contract.total_value,
        paymentTerms=contract.payment_terms,
        termsConditions=contract.terms_conditions,
        pdfUrl=None,
        hasPdf=False,
        providerSignature=contract.provider_signature,
        signedAt=contract.signed_at,
        clientSignatureTimestamp=contract.client_signature_timestamp,
        createdAt=contract.created_at
    )


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a contract"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if data.title is not None:
        contract.title = data.title
    if data.description is not None:
        contract.description = data.description
    if data.contractType is not None:
        contract.contract_type = data.contractType
    if data.status is not None:
        # Validate status transition
        valid_statuses = ['new', 'signed', 'scheduled', 'active', 'cancelled']
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        # Prevent manual completion - completed status is automatic only
        if data.status == 'completed':
            raise HTTPException(
                status_code=400, 
                detail="Cannot manually set status to 'completed'. Contracts are automatically completed when the end date passes."
            )
        
        # Validate status transition logic
        from ..services.status_automation import validate_status_transition
        if not validate_status_transition(contract.status, data.status):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from '{contract.status}' to '{data.status}'"
            )
        
        contract.status = data.status
    if data.startDate is not None:
        contract.start_date = data.startDate
    if data.endDate is not None:
        contract.end_date = data.endDate
    if data.totalValue is not None:
        contract.total_value = data.totalValue
    if data.paymentTerms is not None:
        contract.payment_terms = data.paymentTerms
    if data.termsConditions is not None:
        contract.terms_conditions = data.termsConditions
    
    db.commit()
    db.refresh(contract)
    
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    pdf_url = get_pdf_url(contract.pdf_key)
    return ContractResponse(
        id=contract.id,
        public_id=contract.public_id,
        clientId=contract.client_id,
        clientPublicId=client.public_id if client else None,
        clientName=client.business_name if client else "Unknown",
        clientEmail=client.email if client else None,
        title=contract.title,
        description=contract.description,
        contractType=contract.contract_type,
        status=contract.status,
        startDate=contract.start_date,
        endDate=contract.end_date,
        totalValue=contract.total_value,
        paymentTerms=contract.payment_terms,
        termsConditions=contract.terms_conditions,
        pdfUrl=pdf_url,
        hasPdf=bool(contract.pdf_key),
        providerSignature=contract.provider_signature,
        signedAt=contract.signed_at,
        clientSignatureTimestamp=contract.client_signature_timestamp,
        createdAt=contract.created_at
    )


@router.post("/{contract_id}/sign-provider")
async def sign_contract_as_provider(
    contract_id: int,
    data: ProviderSignatureRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Provider signs the contract - OPTIMIZED FOR SPEED
    
    Performance improvements:
    - PDF regeneration moved to background job (saves 5-30 seconds)
    - Email sending moved to background job (saves 1-5 seconds)
    - Client count increment moved to background job
    - Only essential database updates in main request
    - Response time: ~100-500ms instead of 5-30 seconds
    """
    logger.info(f"🖊️ Provider signing contract {contract_id} (FAST MODE)")
    
    # Get contract and verify ownership (with index: idx_contracts_user_id)
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify contract has client signature (check both signature and timestamp)
    if not contract.client_signature and not contract.client_signature_timestamp:
        raise HTTPException(status_code=400, detail="Contract must be signed by client first")
    
    # Check if contract is already signed by provider
    if contract.signed_at:
        logger.warning(f"⚠️ Contract {contract_id} already signed by provider, skipping duplicate")
        raise HTTPException(status_code=400, detail="Contract already signed by provider")
    
    # Get client (with index: idx_clients_id)
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get business config (with index: idx_business_configs_user_id)
    business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    
    # Determine which signature to use
    signature_to_use = data.signature_data
    if data.use_default_signature and business_config and business_config.signature_url:
        # Use the default signature from onboarding - fetch it as base64
        try:
            default_sig_url = generate_presigned_url(business_config.signature_url)
            # Download and convert to base64
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as http_client:  # 5 second timeout
                response = await http_client.get(default_sig_url)
                if response.status_code == 200:
                    import base64
                    signature_to_use = f"data:image/png;base64,{base64.b64encode(response.content).decode()}"
                    logger.info("✅ Using default signature from onboarding")
                else:
                    logger.warning(f"⚠️ Failed to fetch default signature, using provided signature")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch default signature: {e}, using provided signature")
    
    # CRITICAL: Only update essential fields for immediate response
    contract.provider_signature = signature_to_use
    contract.signed_at = datetime.utcnow()
    contract.signature_timestamp = datetime.utcnow()
    contract.signature_ip = request.client.host if request.client else None
    contract.signature_user_agent = request.headers.get("user-agent")
    contract.status = "signed"  # Fully signed by both parties
    contract.start_date = datetime.utcnow()  # Set start date to signing date
    
    # Commit immediately for fast response
    db.commit()
    db.refresh(contract)
    
    logger.info(f"✅ Contract {contract_id} signed by provider in database (FAST)")
    
    # BACKGROUND JOBS: Move slow operations to async workers
    try:
        from arq import create_pool
        from .config import REDIS_URL
        
        # Create ARQ connection pool
        redis_pool = await create_pool(REDIS_URL)
        
        # Queue PDF regeneration job (5-30 seconds → background)
        await redis_pool.enqueue_job(
            'regenerate_contract_pdf_job',
            contract_id,
            current_user.id,
            "provider"
        )
        logger.info(f"📄 PDF regeneration queued for contract {contract_id}")
        
        # Queue email sending job (1-5 seconds → background)
        await redis_pool.enqueue_job(
            'send_contract_emails_job',
            contract_id,
            current_user.id,
            "provider_signed"
        )
        logger.info(f"📧 Email notifications queued for contract {contract_id}")
        
        # Queue client count increment (database write → background)
        await redis_pool.enqueue_job(
            'increment_client_count_job',
            current_user.id
        )
        logger.info(f"📊 Client count increment queued for user {current_user.id}")
        
        await redis_pool.close()
        
    except Exception as e:
        logger.error(f"⚠️ Failed to queue background jobs: {e}")
        # Continue with response even if background jobs fail
        # Fallback: increment client count synchronously as critical operation
        try:
            from ..plan_limits import increment_client_count
            increment_client_count(current_user, db)
            logger.info(f"📊 Client count incremented synchronously as fallback")
        except Exception as fallback_error:
            logger.error(f"❌ Fallback client count increment failed: {fallback_error}")
    
    logger.info(f"🚀 Contract {contract_id} signing completed in FAST MODE")
    
    # Return immediate response with current PDF (will be updated by background job)
    from .upload import get_pdf_url
    pdf_url = get_pdf_url(contract.pdf_key) if contract.pdf_key else None
    
    return ContractResponse(
        id=contract.id,
        public_id=contract.public_id,
        clientId=contract.client_id,
        clientPublicId=client.public_id,
        clientName=client.business_name,
        clientEmail=client.email,
        title=contract.title,
        description=contract.description,
        contractType=contract.contract_type,
        status=contract.status,
        startDate=contract.start_date,
        endDate=contract.end_date,
        totalValue=contract.total_value,
        paymentTerms=contract.payment_terms,
        termsConditions=contract.terms_conditions,
        pdfUrl=pdf_url,
        hasPdf=bool(contract.pdf_key),
        providerSignature=contract.provider_signature,
        signedAt=contract.signed_at,
        clientSignatureTimestamp=contract.client_signature_timestamp,
        createdAt=contract.created_at
    )


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a contract and its related invoices"""
    from ..models_invoice import Invoice
    
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Delete related invoices first to avoid foreign key constraint violation
    db.query(Invoice).filter(Invoice.contract_id == contract_id).delete()
    
    db.delete(contract)
    db.commit()
    return {"message": "Contract deleted"}
