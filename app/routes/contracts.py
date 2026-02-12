import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models import User, Client, Contract, BusinessConfig
from ..auth import get_current_user
from .upload import generate_presigned_url
from ..email_service import send_contract_fully_executed_email, send_provider_contract_signed_confirmation
from ..utils.sanitization import sanitize_string

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

def get_pdf_url(pdf_key: Optional[str], contract_public_id: Optional[str] = None) -> Optional[str]:
    """Generate backend URL for PDF if key exists (avoids CORS issues)"""
    if not pdf_key or not contract_public_id:
        return None
    try:
        from ..config import FRONTEND_URL
        # Determine the backend base URL based on the frontend URL
        if "localhost" in FRONTEND_URL:
            backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace("localhost:5174", "localhost:8000")
        else:
            backend_base = "https://api.cleanenroll.com"
        
        return f"{backend_base}/contracts/pdf/public/{contract_public_id}"
    except Exception:
        return None

@router.get("", response_model=List[ContractResponse])
async def get_contracts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client_id: Optional[int] = Query(None, description="Filter contracts by client ID"),
    include_all: bool = Query(False, description="Include contracts in all onboarding statuses (not just completed)")
):
    """Get all contracts for the current user, optionally filtered by client_id"""
    query = db.query(Contract).filter(Contract.user_id == current_user.id)
    
    # Only filter by onboarding status if include_all is False
    if not include_all:
        query = query.filter(Contract.client_onboarding_status == "completed")
    
    if client_id:
        query = query.filter(Contract.client_id == client_id)
    
    contracts = query.order_by(Contract.created_at.desc()).all()
    
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
        pdf_url = get_pdf_url(c.pdf_key, c.public_id)
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

@router.post("/initiate", response_model=dict)
async def initiate_contract_process(
    data: ContractCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate contract process by sending form to client.
    Contract will only be created after client signs and schedules.
    """
    logger.info(f"📥 Initiating contract process for user_id: {current_user.id}")
    
    # Verify client belongs to user
    client = db.query(Client).filter(Client.id == data.clientId, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Store contract template data in client record for later use
    client.pending_contract_title = data.title
    client.pending_contract_description = data.description
    client.pending_contract_type = data.contractType
    client.pending_contract_start_date = data.startDate
    client.pending_contract_end_date = data.endDate
    client.pending_contract_total_value = data.totalValue
    client.pending_contract_payment_terms = data.paymentTerms
    client.pending_contract_terms_conditions = data.termsConditions
    
    # Update client status to indicate contract process initiated
    client.status = "contract_sent"
    
    db.commit()
    
    # TODO: Send email to client with form link
    # For now, return success with form URL
    form_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/form/{current_user.public_id}/office?clientId={client.public_id}"
    
    return {
        "success": True,
        "message": "Contract process initiated. Client will receive form link.",
        "formUrl": form_url,
        "clientId": client.id
    }


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
        valid_statuses = ['new', 'signed', 'active', 'cancelled']
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
        
        # Send email notification for contract cancellation
        if data.status == "cancelled":
            try:
                client = db.query(Client).filter(Client.id == contract.client_id).first()
                if client and client.email:
                    # Update client status to cancelled as well
                    client.status = "cancelled"
                    
                    # Get business config for email customization
                    business_config = db.query(BusinessConfig).filter(
                        BusinessConfig.user_id == current_user.id
                    ).first()
                    
                    business_name = business_config.business_name if business_config and business_config.business_name else "CleanEnroll"
                    
                    from ..email_service import send_contract_cancelled_email
                    await send_contract_cancelled_email(
                        client_email=client.email,
                        client_name=sanitize_string(client.contact_name or client.business_name),
                        contract_title=sanitize_string(contract.title),
                        business_name=sanitize_string(business_name),
                        business_config=business_config
                    )
                    logger.info(f"👤 Client {client.id} status updated to cancelled")
                else:
                    logger.warning(f"⚠️ No email found for client {contract.client_id}, skipping cancellation notification")
            except Exception as e:
                logger.error(f"❌ Failed to send contract cancellation email: {e}")
                # Don't fail the request if email fails
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
    pdf_url = get_pdf_url(contract.pdf_key, contract.public_id)
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
    """Provider signs the contract and sends notification to client"""
    # Get contract and verify ownership
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    logger.info(f"📋 Contract {contract_id} signature status: client_signature={bool(contract.client_signature)}, client_signature_timestamp={contract.client_signature_timestamp}")
    if contract.client_signature:
        logger.info(f"📋 Client signature format: {contract.client_signature[:100]}...")
        logger.info(f"📋 Client signature is base64: {contract.client_signature.startswith('data:image')}")
    
    # Verify contract has client signature (check both signature and timestamp)
    if not contract.client_signature and not contract.client_signature_timestamp:
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
    
    # Determine which signature to use
    signature_to_use = data.signature_data
    if data.use_default_signature and business_config and business_config.signature_url:
        # Use the default signature from onboarding - fetch it as base64
        try:
            default_sig_url = generate_presigned_url(business_config.signature_url)
            # Download and convert to base64
            import httpx
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(default_sig_url)
                if response.status_code == 200:
                    import base64
                    signature_to_use = f"data:image/png;base64,{base64.b64encode(response.content).decode()}"
                else:
                    logger.warning(f"⚠️ Failed to fetch default signature, using provided signature")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch default signature: {e}, using provided signature")
    
    # Update contract with provider signature
    contract.provider_signature = signature_to_use  # Store the signature image
    contract.signed_at = datetime.utcnow()
    contract.signature_timestamp = datetime.utcnow()
    contract.signature_ip = request.client.host if request.client else None
    contract.signature_user_agent = request.headers.get("user-agent")
    contract.status = "signed"  # Fully signed by both parties
    contract.start_date = datetime.utcnow()  # Set start date to signing date
    
    # Update client status from "pending_signature" to "new_lead"
    # NOW the client will appear in the provider's client list (after both parties signed)
    if client.status == "pending_signature":
        client.status = "new_lead"
        logger.info(f"✅ Client {client.id} status updated to 'new_lead' after provider signature")
    
    db.commit()
    db.refresh(contract)
    
    # NOTE: Client count is NOT incremented here
    # Client is only counted as "completed" after BOTH:
    # 1. Contract is fully signed (this step)
    # 2. Schedule is accepted by provider (client_onboarding_status = "completed")
    # The increment happens in schedules.py when provider accepts the schedule
    
    # Regenerate PDF with provider signature
    try:
        import hashlib
        from .contracts_pdf import generate_contract_html, html_to_pdf, calculate_quote
        from .upload import get_r2_client, R2_BUCKET_NAME
        
        # Get form data for regeneration
        form_data = client.form_data if client.form_data else {}
        quote = calculate_quote(business_config, form_data)
        
        # Debug the signatures being passed to HTML generation
        logger.info(f"🖊️ [PROVIDER SIGN] Client signature: {'SET (' + str(len(contract.client_signature)) + ' chars)' if contract.client_signature else 'NOT SET'}")
        # Generate HTML with both signatures - use contract's created_at for consistent dates
        html = await generate_contract_html(
            business_config,
            client,
            form_data,
            quote,
            db,
            client_signature=contract.client_signature,
            provider_signature=signature_to_use,
            contract_created_at=contract.created_at,
            contract_public_id=contract.public_id
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
    except Exception as e:
        logger.error(f"Failed to regenerate PDF with provider signature: {e}")
        # Continue even if PDF regeneration fails
    
    # Prepare email data
    pdf_url = get_pdf_url(contract.pdf_key, contract.public_id) if contract.pdf_key else None
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
                contract_pdf_url=pdf_url,
                contract_public_id=contract.public_id
            )
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
        except Exception as e:
            logger.error(f"Failed to send provider email: {e}")
            # Don't fail the signing if email fails
    pdf_url = get_pdf_url(contract.pdf_key, contract.public_id)
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
    
    try:
        # Delete related invoices first to avoid foreign key constraint violation
        deleted_invoices = db.query(Invoice).filter(Invoice.contract_id == contract_id).delete()
        logger.info(f"🗑️ Deleted {deleted_invoices} invoices for contract {contract_id}")
        
        # Delete the contract
        db.delete(contract)
        db.commit()
        
        logger.info(f"✅ Contract {contract_id} and related data deleted successfully")
        return {"message": "Contract deleted"}
        
    except Exception as e:
        logger.error(f"❌ Failed to delete contract {contract_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete contract")


class BatchDeleteRequest(BaseModel):
    contract_ids: List[int]


@router.post("/batch-delete")
async def batch_delete_contracts(
    data: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete multiple contracts and their related data"""
    from ..models_invoice import Invoice
    
    if not data.contract_ids:
        raise HTTPException(status_code=400, detail="No contract IDs provided")
    
    try:
        # Verify all contracts belong to the user
        contracts = db.query(Contract).filter(
            Contract.id.in_(data.contract_ids),
            Contract.user_id == current_user.id
        ).all()
        
        if len(contracts) != len(data.contract_ids):
            raise HTTPException(status_code=404, detail="One or more contracts not found")
        
        # Delete related invoices for all contracts
        deleted_invoices = db.query(Invoice).filter(
            Invoice.contract_id.in_(data.contract_ids)
        ).delete(synchronize_session=False)
        logger.info(f"🗑️ Deleted {deleted_invoices} invoices for {len(data.contract_ids)} contracts")
        
        # Delete all contracts
        deleted_count = db.query(Contract).filter(
            Contract.id.in_(data.contract_ids),
            Contract.user_id == current_user.id
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"✅ Batch deleted {deleted_count} contracts and related data")
        return {
            "message": f"Successfully deleted {deleted_count} contracts",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to batch delete contracts: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete contracts")


@router.post("/{contract_id}/send-square-invoice-email")
async def send_square_invoice_email(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send Square invoice payment link email to client.
    
    This endpoint sends the invoice email from CleanEnroll's email system
    with the Square payment link. Use this when:
    - The automatic email failed during schedule approval
    - You need to resend the invoice to the client
    - You manually created a Square invoice
    """
    from ..email_service import send_invoice_payment_link_email
    from datetime import timedelta
    
    # Get contract
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check if Square invoice exists
    if not contract.square_invoice_id or not contract.square_invoice_url:
        raise HTTPException(
            status_code=400, 
            detail="No Square invoice found for this contract. Please create a Square invoice first."
        )
    
    # Get client
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if not client or not client.email:
        raise HTTPException(
            status_code=400, 
            detail="Client email not found. Cannot send invoice."
        )
    
    # Get business config
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    business_name = (
        business_config.business_name if business_config 
        else current_user.full_name 
        or current_user.email
    )
    
    try:
        # Determine if recurring
        is_recurring = contract.frequency and contract.frequency not in ["one-time", "One-time"]
        
        # Calculate due date (15 days from now if not set)
        due_date = None
        if contract.square_invoice_created_at:
            due_date = (contract.square_invoice_created_at + timedelta(days=15)).strftime("%B %d, %Y")
        else:
            due_date = (datetime.utcnow() + timedelta(days=15)).strftime("%B %d, %Y")
        
        # Send email
        await send_invoice_payment_link_email(
            to=client.email,
            client_name=sanitize_string(client.business_name or client.contact_name or "Client"),
            business_name=sanitize_string(business_name),
            invoice_number=f"INV-{contract.public_id[:8].upper()}",
            invoice_title=sanitize_string(contract.title or "Cleaning Service"),
            total_amount=contract.total_value or 0,
            currency=contract.currency or "USD",
            due_date=due_date,
            payment_link=contract.square_invoice_url,
            is_recurring=is_recurring,
            recurrence_pattern=contract.frequency if is_recurring else None
        )
        
        logger.info(f"✅ Square invoice email sent to {client.email} for contract {contract_id}")
        
        return {
            "success": True,
            "message": "Invoice email sent successfully",
            "email": client.email,
            "invoice_url": contract.square_invoice_url
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send Square invoice email for contract {contract_id}: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send invoice email: {str(e)}"
        )

