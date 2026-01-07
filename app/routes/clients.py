import logging
import re
import csv
from io import StringIO
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional, List
from ..database import get_db
from ..models import User, Client, BusinessConfig
from ..auth import get_current_user
from ..rate_limiter import create_rate_limiter, rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["Clients"])

# Rate limiters for public form submissions
rate_limit_form_per_ip = create_rate_limiter(
    limit=5,
    window_seconds=60,  # 5 submissions per minute per IP
    key_prefix="form_submit_ip",
    use_ip=True
)

rate_limit_form_global = create_rate_limiter(
    limit=15,
    window_seconds=60,  # 15 submissions per minute globally
    key_prefix="form_submit_global",
    use_ip=False
)


def validate_us_phone(phone: str) -> str:
    """Validate and normalize US phone number"""
    if not phone:
        return phone
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Handle +1 prefix
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]
    
    # US phone numbers should have 10 digits
    if len(digits) != 10:
        raise ValueError("Phone number must be 10 digits for US numbers")
    
    # Format as E.164 for storage
    return f"+1{digits}"


class ClientCreate(BaseModel):
    businessName: str
    contactName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    propertyType: Optional[str] = None
    propertySize: Optional[int] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class ClientUpdate(BaseModel):
    businessName: Optional[str] = None
    contactName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    propertyType: Optional[str] = None
    propertySize: Optional[int] = None
    frequency: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class ClientResponse(BaseModel):
    id: int
    businessName: str
    contactName: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    propertyType: Optional[str]
    propertySize: Optional[int]
    frequency: Optional[str]
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=List[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all clients for the current user"""
    clients = db.query(Client).filter(Client.user_id == current_user.id).order_by(Client.created_at.desc()).all()
    return [
        ClientResponse(
            id=c.id,
            businessName=c.business_name,
            contactName=c.contact_name,
            email=c.email,
            phone=c.phone,
            propertyType=c.property_type,
            propertySize=c.property_size,
            frequency=c.frequency,
            status=c.status,
            notes=c.notes
        )
        for c in clients
    ]


@router.post("", response_model=ClientResponse)
async def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new client"""
    logger.info(f"📥 Creating client for user_id: {current_user.id}")
    
    # Check if user can add more clients
    from ..plan_limits import can_add_client, increment_client_count
    can_add, error_message = can_add_client(current_user, db)
    
    if not can_add:
        logger.warning(f"⚠️ User {current_user.id} reached client limit: {error_message}")
        raise HTTPException(status_code=403, detail=error_message)
    
    client = Client(
        user_id=current_user.id,
        business_name=data.businessName,
        contact_name=data.contactName,
        email=data.email,
        phone=data.phone,
        property_type=data.propertyType,
        property_size=data.propertySize,
        frequency=data.frequency,
        notes=data.notes,
        status="new_lead"
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # Increment client count after successful creation
    increment_client_count(current_user, db)
    logger.info(f"✅ Client created: id={client.id}, client count: {current_user.clients_this_month}")
    return ClientResponse(
        id=client.id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes
    )


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a client"""
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if data.businessName is not None:
        client.business_name = data.businessName
    if data.contactName is not None:
        client.contact_name = data.contactName
    if data.email is not None:
        client.email = data.email
    if data.phone is not None:
        client.phone = data.phone
    if data.propertyType is not None:
        client.property_type = data.propertyType
    if data.propertySize is not None:
        client.property_size = data.propertySize
    if data.frequency is not None:
        client.frequency = data.frequency
    if data.status is not None:
        client.status = data.status
    if data.notes is not None:
        client.notes = data.notes
    
    db.commit()
    db.refresh(client)
    
    return ClientResponse(
        id=client.id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes
    )


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a client"""
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(client)
    db.commit()
    return {"message": "Client deleted"}


class BatchDeleteRequest(BaseModel):
    clientIds: List[int]


@router.post("/batch-delete")
async def batch_delete_clients(
    data: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Batch delete multiple clients"""
    if not data.clientIds:
        raise HTTPException(status_code=400, detail="No client IDs provided")
    
    # Verify all clients belong to the current user and delete them
    deleted_count = 0
    for client_id in data.clientIds:
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.user_id == current_user.id
        ).first()
        if client:
            db.delete(client)
            deleted_count += 1
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {deleted_count} client(s)",
        "deletedCount": deleted_count
    }


@router.get("/export")
async def export_clients_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Export clients as CSV with optional filters"""
    # Base query
    query = db.query(Client).filter(Client.user_id == current_user.id)
    
    # Apply status filter
    if status and status != "all":
        query = query.filter(Client.status == status)
    
    # Apply search filter (by name or email)
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            (Client.business_name.ilike(search_term)) |
            (Client.contact_name.ilike(search_term)) |
            (Client.email.ilike(search_term))
        )
    
    # Apply date range filter
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Client.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Client.created_at <= end_dt)
        except ValueError:
            pass
    
    # Get filtered clients
    clients = query.order_by(Client.created_at.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID',
        'Business Name',
        'Contact Name',
        'Email',
        'Phone',
        'Property Type',
        'Property Size (sq ft)',
        'Frequency',
        'Status',
        'Notes',
        'Created At'
    ])
    
    # Write data
    for client in clients:
        writer.writerow([
            client.id,
            client.business_name or '',
            client.contact_name or '',
            client.email or '',
            client.phone or '',
            client.property_type or '',
            client.property_size or '',
            client.frequency or '',
            client.status or '',
            client.notes or '',
            client.created_at.strftime('%Y-%m-%d %H:%M:%S') if client.created_at else ''
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



class PublicClientCreate(BaseModel):
    """Schema for public form submission - uses owner's Firebase UID"""
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
    formData: Optional[dict] = None  # Store all form fields as JSON
    clientSignature: Optional[str] = None  # Base64 signature from client
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class PublicSubmitResponse(BaseModel):
    client: ClientResponse
    contractPdfUrl: Optional[str] = None
    message: str


@router.post("/public/submit")
async def submit_public_form(
    data: PublicClientCreate,
    request: Request,
    db: Session = Depends(get_db),
    _ip: None = Depends(rate_limit_form_per_ip),
    _global: None = Depends(rate_limit_form_global)
):
    """
    Public endpoint for clients to submit intake forms.
    Rate limited: 5 per minute per IP, 15 per minute globally.
    Uses the business owner's Firebase UID to associate the client.
    Automatically generates a PDF contract.
    No authentication required - this is accessed via shareable link.
    """
    import json
    import hashlib
    from ..models import Contract
    from .contracts_pdf import calculate_quote, generate_contract_html, html_to_pdf
    from .upload import get_r2_client, generate_presigned_url, R2_BUCKET_NAME
    from ..email_service import send_new_client_notification, send_form_submission_confirmation
    
    # Capture signature audit data
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "unknown")
    
    logger.info(f"📥 Public form submission for owner UID: {data.ownerUid}")
    
    # Find the user by Firebase UID
    user = db.query(User).filter(User.firebase_uid == data.ownerUid).first()
    if not user:
        logger.error(f"❌ User not found for Firebase UID: {data.ownerUid}")
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Create the client associated with the business owner
    client = Client(
        user_id=user.id,
        business_name=data.businessName,
        contact_name=data.contactName,
        email=data.email,
        phone=data.phone,
        property_type=data.propertyType,
        property_size=data.propertySize,
        frequency=data.frequency,
        notes=data.notes,
        form_data=data.formData,  # Store structured form data
        status="new_lead"
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    logger.info(f"✅ Public form client created: id={client.id} for user_id={user.id}")
    
    # Try to generate PDF contract
    contract_pdf_url = None
    try:
        # Get business config for pricing calculation
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        
        logger.info(f"📋 Config found: {config is not None}, formData provided: {data.formData is not None}")
        
        if config and data.formData:
            # Calculate quote
            quote = calculate_quote(config, data.formData)
            logger.info(f"💰 Quote calculated: {quote}")
            
            # Generate HTML (without client signature - they'll sign after reviewing)
            html = await generate_contract_html(
                config, 
                client, 
                data.formData, 
                quote,
                None  # No signature yet - client will sign after reviewing PDF
            )
            logger.info(f"📄 HTML generated, length: {len(html)} chars")
            
            # Generate PDF
            logger.info("🔄 Starting PDF generation...")
            pdf_bytes = await html_to_pdf(html)
            logger.info(f"✅ PDF generated: {len(pdf_bytes)} bytes")
            
            # Upload PDF to R2
            from datetime import datetime
            
            pdf_key = f"contracts/{user.firebase_uid}/{client.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Upload to R2 and get URL
            try:
                r2_client = get_r2_client()
                r2_client.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=pdf_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf"
                )
                
                # Generate presigned URL for download
                contract_pdf_url = generate_presigned_url(pdf_key)
                
                # Calculate PDF hash for integrity verification
                pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
                
                logger.info(f"✅ Contract PDF uploaded: {pdf_key}")
            except Exception as upload_err:
                logger.warning(f"⚠️ Failed to upload PDF to R2: {upload_err}")
                pdf_key = None
                pdf_hash = None
            
            # Create contract record - awaiting client signature
            contract = Contract(
                user_id=user.id,
                client_id=client.id,
                title=f"Service Agreement - {client.business_name}",
                description=f"Auto-generated contract for {quote['frequency']} cleaning service",
                contract_type="recurring" if quote.get('frequency', '') not in ['One-time', 'one-time'] else "one-time",
                status="new",  # New lead/contract awaiting signatures
                total_value=quote['final_price'],
                currency="USD",
                payment_terms=f"Net {config.payment_due_days or 15} days",
                pdf_key=pdf_key,
                pdf_hash=pdf_hash,
            )
            db.add(contract)
            db.commit()
            
            logger.info(f"✅ Contract record created: id={contract.id}")
            
    except Exception as pdf_err:
        import traceback
        logger.warning(f"⚠️ Failed to generate contract PDF: {pdf_err}")
        logger.warning(f"Traceback: {traceback.format_exc()}")
        # Continue without PDF - client submission still succeeds
    
    # Send email notifications (async, don't block response)
    try:
        # Get business config for business name
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"
        
        # Notify business owner of new submission
        if user.email:
            await send_new_client_notification(
                to=user.email,
                business_name=business_name,
                client_name=data.contactName or data.businessName,
                client_email=data.email or "Not provided",
                property_type=data.propertyType or "Not specified",
            )
            logger.info(f"📧 Notification email sent to business owner: {user.email}")
        
        # Send confirmation to client
        if data.email:
            await send_form_submission_confirmation(
                to=data.email,
                client_name=data.contactName or data.businessName,
                business_name=business_name,
                property_type=data.propertyType or "Property",
            )
            logger.info(f"📧 Confirmation email sent to client: {data.email}")
            
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to send email notifications: {email_err}")
        # Continue - email failure shouldn't fail the submission
    
    return {
        "client": ClientResponse(
            id=client.id,
            businessName=client.business_name,
            contactName=client.contact_name,
            email=client.email,
            phone=client.phone,
            propertyType=client.property_type,
            propertySize=client.property_size,
            frequency=client.frequency,
            status=client.status,
            notes=client.notes
        ),
        "contractPdfUrl": contract_pdf_url,
        "message": "Form submitted successfully" + (" - Contract generated" if contract_pdf_url else "")
    }


class SignContractRequest(BaseModel):
    clientId: int
    signature: str


@router.post("/public/sign-contract")
async def sign_contract(
    data: SignContractRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for clients to sign their contract after reviewing the PDF.
    Updates the contract with the client's signature and audit trail.
    """
    import hashlib
    from datetime import datetime
    from ..models import Contract
    from .contracts_pdf import generate_contract_html, html_to_pdf
    from .upload import get_r2_client, generate_presigned_url, R2_BUCKET_NAME
    from ..email_service import send_contract_signed_notification
    
    # Capture signature audit data
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "unknown")
    
    logger.info(f"📝 Contract signing request for client_id: {data.clientId}")
    
    # Find the client
    client = db.query(Client).filter(Client.id == data.clientId).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Find the contract for this client
    contract = db.query(Contract).filter(Contract.client_id == data.clientId).order_by(Contract.created_at.desc()).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get the user (business owner)
    user = db.query(User).filter(User.id == client.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Update contract with client signature audit trail
    contract.client_signature = data.signature
    contract.client_signature_ip = client_ip
    contract.client_signature_user_agent = user_agent[:500] if user_agent else None
    contract.client_signature_timestamp = datetime.now()
    # Status remains 'new' until both parties sign (provider signs last)
    
    # Upload client signature to R2 for PDF rendering
    client_signature_url = None
    if data.signature and data.signature.startswith("data:image"):
        try:
            import base64
            import uuid
            # Extract base64 data from data URL
            header, encoded = data.signature.split(",", 1)
            signature_bytes = base64.b64decode(encoded)
            
            # Upload to R2
            signature_key = f"signatures/clients/{user.firebase_uid}/{uuid.uuid4()}.png"
            r2_client = get_r2_client()
            r2_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=signature_key,
                Body=signature_bytes,
                ContentType="image/png"
            )
            
            # Generate presigned URL (7 days max for R2)
            client_signature_url = generate_presigned_url(signature_key, expiration=604800)  # 7 days
            logger.info(f"✅ Client signature uploaded to R2: {signature_key}")
        except Exception as sig_err:
            logger.warning(f"⚠️ Failed to upload client signature to R2: {sig_err}")
    
    # Regenerate PDF with client signature
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        
        if config and client.form_data:
            form_data = client.form_data
            
            # Log old PDF key
            old_pdf_key = contract.pdf_key
            logger.info(f"📄 Old PDF key: {old_pdf_key}")
            
            # Calculate quote for regeneration
            from .contracts_pdf import calculate_quote
            quote = calculate_quote(config, form_data)
            
            # Get provider signature URL if exists
            provider_signature_url = None
            if contract.provider_signature and contract.provider_signature.startswith("data:image"):
                # Provider signature is base64, need to upload it too if not already done
                provider_signature_url = contract.provider_signature
            
            # Generate HTML with signature URLs
            html = await generate_contract_html(
                config, 
                client, 
                form_data, 
                quote,
                client_signature=client_signature_url or data.signature,  # Use URL if available
                provider_signature=provider_signature_url
            )
            
            # Verify signature URL is in HTML
            if client_signature_url and client_signature_url in html:
                logger.info("✅ Client signature URL IS in generated HTML")
            elif data.signature in html:
                logger.info("✅ Client signature (base64) IS in generated HTML")
            else:
                logger.warning("⚠️ Client signature NOT found in generated HTML!")
            
            # Generate PDF
            pdf_bytes = await html_to_pdf(html)
            
            # Calculate new PDF hash
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            
            # Upload updated PDF to R2
            pdf_key = f"contracts/{user.firebase_uid}/{client.id}-signed-{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            try:
                r2_client = get_r2_client()
                r2_client.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=pdf_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf"
                )
                
                contract.pdf_key = pdf_key
                contract.pdf_hash = pdf_hash
                
                logger.info(f"✅ Signed contract PDF uploaded: {pdf_key}")
                logger.info(f"📝 Updated contract.pdf_key from {old_pdf_key} to {pdf_key}")
            except Exception as upload_err:
                logger.warning(f"⚠️ Failed to upload signed PDF: {upload_err}")
                
    except Exception as pdf_err:
        logger.warning(f"⚠️ Failed to regenerate signed PDF: {pdf_err}")
    
    db.commit()
    db.refresh(contract)
    
    logger.info(f"✅ Contract signed by client: contract_id={contract.id}")
    
    # Generate presigned URL for the new signed PDF
    signed_pdf_url = None
    if contract.pdf_key:
        try:
            signed_pdf_url = generate_presigned_url(contract.pdf_key, expiration=604800)  # 7 days
            logger.info(f"✅ Generated presigned URL for signed contract PDF")
        except Exception as url_err:
            logger.warning(f"⚠️ Failed to generate presigned URL: {url_err}")
    
    # Send notification to business owner
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"
        
        if user.email:
            await send_contract_signed_notification(
                to=user.email,
                business_name=business_name,
                client_name=client.contact_name or client.business_name,
                contract_title=contract.title,
            )
            logger.info(f"📧 Contract signed notification sent to: {user.email}")
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to send contract signed notification: {email_err}")
    
    return {
        "success": True,
        "message": "Contract signed successfully. Awaiting service provider signature.",
        "signedPdfUrl": signed_pdf_url
    }


class ScheduleDecisionRequest(BaseModel):
    action: str  # 'confirm' or 'request_change'
    proposed_start_time: Optional[str] = None
    proposed_end_time: Optional[str] = None


@router.post("/{client_id}/schedule-decision")
async def handle_schedule_decision(
    client_id: int,
    data: ScheduleDecisionRequest,
    db: Session = Depends(get_db)
):
    """
    Handle provider's decision on client's scheduled time
    Provider can confirm or propose a different time
    """
    from ..email_service import send_email
    
    try:
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get business config for business name
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == client.user_id).first()
        business_name = config.business_name if config else "Your Service Provider"
        
        if data.action == 'confirm':
            # Provider confirmed the client's selected time
            client.scheduling_status = 'confirmed'
            db.commit()
            
            # Send confirmation email to client
            if client.email:
                content = f"""
                <p>Hi {client.contact_name or client.business_name},</p>
                <p>Great news! <strong>{business_name}</strong> has confirmed your preferred cleaning schedule.</p>
                <div style="background: #f0fdf4; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #22c55e;">
                  <p style="color: #15803d; font-weight: 600; margin-bottom: 12px;">✓ Confirmed Cleaning Date & Time</p>
                  <p style="color: #15803d; font-size: 16px; margin: 8px 0;">
                    📅 {datetime.fromisoformat(client.scheduled_start_time.replace('Z', '+00:00')).strftime('%A, %B %d, %Y')}
                  </p>
                  <p style="color: #15803d; font-size: 16px; margin: 8px 0;">
                    ⏰ {datetime.fromisoformat(client.scheduled_start_time.replace('Z', '+00:00')).strftime('%I:%M %p')} - {datetime.fromisoformat(client.scheduled_end_time.replace('Z', '+00:00')).strftime('%I:%M %p')}
                  </p>
                </div>
                <p>Your first cleaning is all set! We look forward to serving you.</p>
                """
                
                await send_email(
                    to=client.email,
                    subject=f"Cleaning Schedule Confirmed - {business_name}",
                    title="Your Cleaning is Scheduled! 🎉",
                    content_html=content
                )
                
            logger.info(f"✅ Provider confirmed schedule for client {client_id}")
            
        elif data.action == 'request_change':
            # Provider requested a different time
            if not data.proposed_start_time or not data.proposed_end_time:
                raise HTTPException(status_code=400, detail="Proposed times are required")
            
            # Update scheduling status
            client.scheduling_status = 'provider_requested_change'
            
            # Store proposed times temporarily (you might want to add these fields to the model)
            # For now, we'll send them via email
            db.commit()
            
            # Send notification to client with provider's proposed time
            if client.email:
                proposed_start = datetime.fromisoformat(data.proposed_start_time.replace('Z', '+00:00'))
                proposed_end = datetime.fromisoformat(data.proposed_end_time.replace('Z', '+00:00'))
                
                content = f"""
                <p>Hi {client.contact_name or client.business_name},</p>
                <p><strong>{business_name}</strong> has reviewed your preferred cleaning schedule and would like to propose an alternative time that better fits their availability.</p>
                
                <div style="background: #fef3c7; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #f59e0b;">
                  <p style="color: #92400e; font-weight: 600; margin-bottom: 12px;">📅 Your Selected Time</p>
                  <p style="color: #92400e; font-size: 15px; margin: 8px 0;">
                    {datetime.fromisoformat(client.scheduled_start_time.replace('Z', '+00:00')).strftime('%A, %B %d, %Y')}
                  </p>
                  <p style="color: #92400e; font-size: 15px; margin: 8px 0;">
                    {datetime.fromisoformat(client.scheduled_start_time.replace('Z', '+00:00')).strftime('%I:%M %p')} - {datetime.fromisoformat(client.scheduled_end_time.replace('Z', '+00:00')).strftime('%I:%M %p')}
                  </p>
                </div>
                
                <div style="background: #dbeafe; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #3b82f6;">
                  <p style="color: #1e40af; font-weight: 600; margin-bottom: 12px;">✨ Provider's Proposed Time</p>
                  <p style="color: #1e40af; font-size: 16px; margin: 8px 0;">
                    📅 {proposed_start.strftime('%A, %B %d, %Y')}
                  </p>
                  <p style="color: #1e40af; font-size: 16px; margin: 8px 0;">
                    ⏰ {proposed_start.strftime('%I:%M %p')} - {proposed_end.strftime('%I:%M %p')}
                  </p>
                </div>
                
                <p>The service provider will reach out to you shortly to confirm this new time or discuss other options that work for both of you.</p>
                <p style="color: #64748b; font-size: 14px; margin-top: 20px;">
                  If you have any questions or concerns, please contact {business_name} directly.
                </p>
                """
                
                await send_email(
                    to=client.email,
                    subject=f"Alternative Cleaning Time Proposed - {business_name}",
                    title="Schedule Change Request",
                    content_html=content
                )
                
            logger.info(f"✅ Provider requested schedule change for client {client_id}")
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        return {
            "success": True,
            "message": f"Schedule {data.action} processed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error handling schedule decision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
