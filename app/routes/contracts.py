import logging
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
    clientId: int
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

    class Config:
        from_attributes = True


class ProviderSignatureRequest(BaseModel):
    signature_data: str  # Base64 signature image


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
    result = []
    for c in contracts:
        client = db.query(Client).filter(Client.id == c.client_id).first()
        pdf_url = get_pdf_url(c.pdf_key)
        result.append(ContractResponse(
            id=c.id,
            clientId=c.client_id,
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
            createdAt=c.created_at
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
        clientId=contract.client_id,
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
        valid_statuses = ['new', 'signed', 'scheduled', 'active', 'cancelled', 'completed']
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
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
        clientId=contract.client_id,
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
    """Provider signs the contract and sends notification to client"""
    logger.info(f"🖊️ Provider signing contract {contract_id}")
    
    # Get contract and verify ownership
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify contract has client signature
    if not contract.client_signature:
        raise HTTPException(status_code=400, detail="Contract must be signed by client first")
    
    # Check if contract is already signed by provider
    if contract.signed_at:
        logger.warning(f"⚠️ Contract {contract_id} already signed by provider, skipping duplicate")
        raise HTTPException(status_code=400, detail="Contract already signed by provider")
    
    # Get client and business info
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    business_name = business_config.business_name if business_config else "Cleaning Service"
    
    # Update contract with provider signature
    contract.provider_signature = data.signature_data  # Store the signature image
    contract.signed_at = datetime.utcnow()
    contract.signature_timestamp = datetime.utcnow()
    contract.signature_ip = request.client.host if request.client else None
    contract.signature_user_agent = request.headers.get("user-agent")
    contract.status = "signed"  # Fully signed by both parties
    
    db.commit()
    db.refresh(contract)
    
    # Regenerate PDF with provider signature
    logger.info(f"📄 Regenerating contract PDF with provider signature")
    try:
        import hashlib
        from .contracts_pdf import generate_contract_html, html_to_pdf, calculate_quote
        from .upload import get_r2_client, R2_BUCKET_NAME
        
        # Get form data for regeneration
        form_data = client.form_data if client.form_data else {}
        quote = calculate_quote(business_config, form_data)
        
        # Generate HTML with both signatures
        html = await generate_contract_html(
            business_config,
            client,
            form_data,
            quote,
            client_signature=contract.client_signature,
            provider_signature=data.signature_data
        )
        
        # Convert to PDF
        pdf_bytes = await html_to_pdf(html)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Upload to R2
        r2 = get_r2_client()
        pdf_key = f"contracts/{current_user.id}/{contract.id}_signed.pdf"
        r2.put_object(Bucket=R2_BUCKET_NAME, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")
        
        # Update contract with new PDF
        contract.pdf_key = pdf_key
        contract.pdf_hash = pdf_hash
        db.commit()
        
        logger.info(f"✅ Contract PDF regenerated with provider signature: {pdf_key}")
    except Exception as e:
        logger.error(f"Failed to regenerate PDF with provider signature: {e}")
        # Continue even if PDF regeneration fails
    
    # Prepare email data
    pdf_url = get_pdf_url(contract.pdf_key) if contract.pdf_key else None
    service_type = contract.contract_type or "Cleaning Service"
    start_date = contract.start_date.strftime("%B %d, %Y") if contract.start_date else None
    property_address = client.address if hasattr(client, 'address') else None
    business_phone = business_config.business_phone if business_config and hasattr(business_config, 'business_phone') else None
    
    # Send notification email to client
    if client.email:
        try:
            await send_contract_fully_executed_email(
                to=client.email,
                client_name=client.contact_name or client.business_name,
                business_name=business_name,
                contract_title=contract.title,
                contract_id=contract.id,
                service_type=service_type,
                start_date=start_date,
                total_value=contract.total_value,
                property_address=property_address,
                business_phone=business_phone,
                contract_pdf_url=pdf_url
            )
            logger.info(f"✅ Sent fully executed contract email to {client.email}")
        except Exception as e:
            logger.error(f"Failed to send client email: {e}")
            # Don't fail the signing if email fails
    
    # Send confirmation email to provider
    if current_user.email:
        try:
            await send_provider_contract_signed_confirmation(
                to=current_user.email,
                provider_name=current_user.full_name or "Provider",
                contract_id=contract.id,
                client_name=client.business_name,
                property_address=property_address,
                contract_pdf_url=pdf_url
            )
            logger.info(f"✅ Sent provider confirmation email to {current_user.email}")
        except Exception as e:
            logger.error(f"Failed to send provider email: {e}")
            # Don't fail the signing if email fails
    
    logger.info(f"✅ Contract {contract_id} fully signed")
    
    pdf_url = get_pdf_url(contract.pdf_key)
    return ContractResponse(
        id=contract.id,
        clientId=contract.client_id,
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
    """Delete a contract"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    db.delete(contract)
    db.commit()
    return {"message": "Contract deleted"}
