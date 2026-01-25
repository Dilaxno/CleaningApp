import logging
import re
import csv
import uuid
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
from ..rate_limiter import create_rate_limiter, rate_limit_dependency, get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["Clients"])


def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


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
    public_id: Optional[str] = None  # UUID for secure public access
    businessName: str
    contactName: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    propertyType: Optional[str]
    propertySize: Optional[int]
    frequency: Optional[str]
    status: str
    notes: Optional[str]
    form_data: Optional[dict] = None  # Include form_data for detailed view

    class Config:
        from_attributes = True


@router.get("", response_model=List[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all clients for the current user (excludes pending_signature clients)"""
    # Filter out clients with "pending_signature" status - they haven't signed the contract yet
    clients = db.query(Client).filter(
        Client.user_id == current_user.id,
        Client.status != "pending_signature"
    ).order_by(Client.created_at.desc()).all()
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


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific client with detailed information including form_data"""
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return ClientResponse(
        id=client.id,
        public_id=client.public_id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes,
        form_data=client.form_data
    )


@router.post("", response_model=ClientResponse)
async def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new client"""
    logger.info(f"📥 Creating client for user_id: {current_user.id}")
    
    # Check if user can add more clients (but don't increment yet - that happens when contract is signed)
    from ..plan_limits import can_add_client
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
    
    # Note: Client count is incremented when contract is fully signed (both parties)
    logger.info(f"✅ Client created: id={client.id}")
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
    """Delete a client and all related data (contracts, schedules, invoices, proposals)"""
    from ..plan_limits import decrement_client_count
    
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Count related records before deletion for logging
    contracts_count = len(client.contracts)
    schedules_count = len(client.schedules)
    invoices_count = len(client.invoices)
    proposals_count = len(client.scheduling_proposals)
    
    logger.info(f"🗑️ Deleting client {client_id} ({client.contact_name or client.business_name})")
    logger.info(f"   📄 {contracts_count} contract(s)")
    logger.info(f"   📅 {schedules_count} schedule(s)")
    logger.info(f"   🧾 {invoices_count} invoice(s)")
    logger.info(f"   📝 {proposals_count} scheduling proposal(s)")
    
    # Check if client had a fully signed contract (both parties signed)
    # This is when the count was incremented, so we need to decrement
    has_signed_contract = any(
        c.client_signature_timestamp and c.signed_at 
        for c in client.contracts
    )
    
    # Delete client - cascade will automatically delete:
    # - contracts (and their invoices via cascade)
    # - schedules
    # - invoices
    # - scheduling_proposals
    db.delete(client)
    db.commit()
    
    logger.info(f"✅ Client {client_id} and all related data deleted successfully")
    
    # Decrement client count if they had a signed contract
    if has_signed_contract:
        decrement_client_count(current_user, db)
        logger.info(f"📊 Client count decremented for user {current_user.id}: {current_user.clients_this_month}")
    
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
    from ..models_invoice import Invoice
    from ..plan_limits import decrement_client_count
    
    if not data.clientIds:
        raise HTTPException(status_code=400, detail="No client IDs provided")
    
    # Verify all clients belong to the current user and delete them
    deleted_count = 0
    signed_contracts_count = 0
    total_contracts = 0
    total_schedules = 0
    total_invoices = 0
    total_proposals = 0
    
    logger.info(f"🗑️ Batch deleting {len(data.clientIds)} client(s)")
    
    for client_id in data.clientIds:
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.user_id == current_user.id
        ).first()
        if client:
            # Count related records before deletion
            contracts_count = len(client.contracts)
            schedules_count = len(client.schedules)
            invoices_count = len(client.invoices)
            proposals_count = len(client.scheduling_proposals)
            
            total_contracts += contracts_count
            total_schedules += schedules_count
            total_invoices += invoices_count
            total_proposals += proposals_count
            
            logger.info(f"   Deleting client {client_id} ({client.contact_name or client.business_name}): {contracts_count} contracts, {schedules_count} schedules, {invoices_count} invoices, {proposals_count} proposals")
            
            # Check if client had a fully signed contract
            has_signed_contract = any(
                c.client_signature_timestamp and c.signed_at 
                for c in client.contracts
            )
            if has_signed_contract:
                signed_contracts_count += 1
            
            # Get contract IDs for this client
            contract_ids = [c.id for c in client.contracts]
            
            # Delete invoices linked to these contracts first (FK constraint)
            if contract_ids:
                db.query(Invoice).filter(Invoice.contract_id.in_(contract_ids)).delete(synchronize_session=False)
            
            # Delete client - cascade will handle contracts, schedules, invoices, proposals
            db.delete(client)
            deleted_count += 1
    
    db.commit()
    
    logger.info(f"✅ Batch delete complete: {deleted_count} clients, {total_contracts} contracts, {total_schedules} schedules, {total_invoices} invoices, {total_proposals} proposals")
    
    # Decrement client count for each deleted client that had a signed contract
    for _ in range(signed_contracts_count):
        decrement_client_count(current_user, db)
    
    if signed_contracts_count > 0:
        logger.info(f"📊 Client count decremented by {signed_contracts_count} for user {current_user.id}: {current_user.clients_this_month}")
    
    return {
        "message": f"Successfully deleted {deleted_count} client(s)",
        "deletedCount": deleted_count,
        "deletedContracts": total_contracts,
        "deletedSchedules": total_schedules,
        "deletedInvoices": total_invoices,
        "deletedProposals": total_proposals
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
    # Base query - exclude pending_signature clients
    query = db.query(Client).filter(
        Client.user_id == current_user.id,
        Client.status != "pending_signature"
    )
    
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
    quoteAccepted: Optional[bool] = False  # Whether client accepted the quote
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class QuotePreviewRequest(BaseModel):
    """Schema for quote preview - calculates quote without creating client"""
    ownerUid: str
    formData: dict


class QuotePreviewResponse(BaseModel):
    """Response for quote preview"""
    basePrice: float
    discountPercent: float
    discountAmount: float
    addonAmount: float = 0
    addonDetails: List[dict] = []
    finalPrice: float
    estimatedHours: float
    cleaners: int
    pricingModel: str
    frequency: str
    pricingExplanation: str
    quotePending: bool = False


class PublicSubmitResponse(BaseModel):
    client: Optional[ClientResponse] = None
    contractPdfUrl: Optional[str] = None
    jobId: Optional[str] = None
    message: str


@router.post("/public/quote-preview", response_model=QuotePreviewResponse)
async def get_quote_preview(
    data: QuotePreviewRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to calculate and preview quote before form submission.
    No client is created - just returns the calculated quote with explanation.
    """
    from .contracts_pdf import calculate_quote
    
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    logger.info(f"📊 Quote preview request for owner UID: {data.ownerUid} from IP: {client_ip}")
    
    # Find the user by Firebase UID
    user = db.query(User).filter(User.firebase_uid == data.ownerUid).first()
    if not user:
        logger.error(f"❌ User not found for Firebase UID: {data.ownerUid}")
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Get business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        logger.warning(f"⚠️ No business config found for user {user.id}")
        return QuotePreviewResponse(
            basePrice=0,
            discountPercent=0,
            discountAmount=0,
            addonAmount=0,
            addonDetails=[],
            finalPrice=0,
            estimatedHours=0,
            cleaners=1,
            pricingModel="",
            frequency=data.formData.get("cleaningFrequency", ""),
            pricingExplanation="Quote will be provided by the service provider.",
            quotePending=True
        )
    
    # Calculate quote
    quote = calculate_quote(config, data.formData)
    
    # Build pricing explanation
    pricing_model = config.pricing_model or ""
    property_size = int(data.formData.get("squareFootage", 0) or 0)
    num_rooms = int(data.formData.get("numberOfOffices", 0) or data.formData.get("numberOfRooms", 0) or 0)
    frequency = data.formData.get("cleaningFrequency", "")
    
    explanation_parts = []
    
    business_name = config.business_name or "This business"
    
    if quote.get("quote_pending"):
        explanation = "Quote will be provided by the service provider after reviewing your requirements."
    else:
        # Base rate explanation - show business name and rate per metric
        if pricing_model == "sqft" and config.rate_per_sqft:
            explanation_parts.append(f"{business_name} prices their jobs at ${config.rate_per_sqft:.2f} per sq ft")
        elif pricing_model == "room" and config.rate_per_room:
            explanation_parts.append(f"{business_name} prices their jobs at ${config.rate_per_room:.2f} per room")
        elif pricing_model == "hourly" and config.hourly_rate:
            explanation_parts.append(f"{business_name} prices their jobs at ${config.hourly_rate:.2f} per hour")
        elif pricing_model == "flat" and config.flat_rate:
            explanation_parts.append(f"{business_name} prices their jobs at a flat rate of ${config.flat_rate:,.2f}")
        else:
            explanation_parts.append(f"Base service rate: ${quote['base_price']:,.2f}")
        
        # Discount explanation
        if quote['discount_percent'] > 0:
            explanation_parts.append(f"{quote['discount_percent']:.0f}% {frequency.lower()} discount applied")
        
        explanation = " • ".join(explanation_parts)
    
    logger.info(f"✅ Quote preview calculated: ${quote['final_price']:,.2f} for {frequency}")
    
    return QuotePreviewResponse(
        basePrice=quote['base_price'],
        discountPercent=quote['discount_percent'],
        discountAmount=quote['discount_amount'],
        addonAmount=quote.get('addon_amount', 0),
        addonDetails=quote.get('addon_details', []),
        finalPrice=quote['final_price'],
        estimatedHours=quote['estimated_hours'],
        cleaners=quote['cleaners'],
        pricingModel=pricing_model,
        frequency=frequency,
        pricingExplanation=explanation,
        quotePending=quote.get('quote_pending', False)
    )


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
    Contract generation is queued asynchronously to prevent timeouts.
    No authentication required - this is accessed via shareable link.
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    from ..worker import get_redis_settings
    from ..email_service import send_new_client_notification, send_form_submission_confirmation
    
    # Capture client info
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "unknown")
    
    logger.info(f"📥 Public form submission for owner UID: {data.ownerUid} from IP: {client_ip}")
    
    # Note: Rate limiting handles submission abuse prevention
    # No need for additional Redis tracking here
    
    # Strict input validation
    validation_errors = []
    
    # Validate business name (required)
    if not data.businessName or len(data.businessName.strip()) < 2:
        validation_errors.append("Business name must be at least 2 characters")
    elif len(data.businessName) > 200:
        validation_errors.append("Business name must be less than 200 characters")
    
    # Validate email format if provided
    if data.email:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data.email):
            validation_errors.append("Invalid email format")
        elif len(data.email) > 255:
            validation_errors.append("Email must be less than 255 characters")
    
    # Validate phone format if provided
    if data.phone:
        # Remove all non-digit characters for validation
        phone_digits = re.sub(r'\D', '', data.phone)
        if len(phone_digits) < 10 or len(phone_digits) > 15:
            validation_errors.append("Phone number must be between 10-15 digits")
    
    # Validate contact name if provided
    if data.contactName and len(data.contactName) > 200:
        validation_errors.append("Contact name must be less than 200 characters")
    
    # Validate property size if provided
    if data.propertySize and (data.propertySize < 0 or data.propertySize > 1000000):
        validation_errors.append("Property size must be between 0 and 1,000,000 sq ft")
    
    # Validate notes length if provided
    if data.notes and len(data.notes) > 5000:
        validation_errors.append("Notes must be less than 5000 characters")
    
    # Validate formData size (prevent DOS attacks)
    if data.formData:
        import json
        form_data_str = json.dumps(data.formData)
        if len(form_data_str) > 50000:  # 50KB limit
            validation_errors.append("Form data is too large (max 50KB)")
    
    # Return validation errors if any
    if validation_errors:
        logger.warning(f"❌ Validation failed for IP {client_ip}: {validation_errors}")
        raise HTTPException(
            status_code=422,
            detail={"message": "Validation failed", "errors": validation_errors}
        )
    
    # Find the user by Firebase UID
    user = db.query(User).filter(User.firebase_uid == data.ownerUid).first()
    if not user:
        logger.error(f"❌ User not found for Firebase UID: {data.ownerUid}")
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Extract frequency from formData if not provided directly
    frequency = data.frequency
    if not frequency and data.formData:
        frequency = data.formData.get("cleaningFrequency")
    
    # If still no frequency, infer from property type (e.g., move-in-out is always one-time)
    if not frequency and data.propertyType:
        property_type_lower = data.propertyType.lower()
        if 'move' in property_type_lower:
            frequency = "One-time"
        elif 'construction' in property_type_lower or 'post-construction' in property_type_lower:
            frequency = "One-time"
        elif 'event' in property_type_lower:
            frequency = "One-time"
    
    # Create the client associated with the business owner
    # Status is "pending_signature" until client signs the contract
    # This prevents the client from appearing in provider's list before contract is signed
    client = Client(
        user_id=user.id,
        business_name=data.businessName,
        contact_name=data.contactName,
        email=data.email,
        phone=data.phone,
        property_type=data.propertyType,
        property_size=data.propertySize,
        frequency=frequency,
        notes=data.notes,
        form_data=data.formData,  # Store structured form data
        status="pending_signature"  # Will change to "new_lead" after contract is signed
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    logger.info(f"✅ Public form client created: id={client.id} for user_id={user.id} with status=pending_signature")
    
    # Queue contract PDF generation as background job (async to prevent timeout)
    job_id = None
    if data.formData:
        try:
            # Get business config to check if it exists
            config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
            
            if config:
                # Enqueue contract generation job
                redis_settings = get_redis_settings()
                pool = await create_pool(redis_settings)
                
                job = await pool.enqueue_job(
                    'generate_contract_pdf_task',
                    client.id,
                    data.ownerUid,
                    data.formData,
                    data.clientSignature
                )
                
                job_id = job.job_id
                logger.info(f"📋 Contract generation job queued: {job_id}")
            else:
                logger.warning(f"⚠️ No business config found for user {user.id} - skipping contract generation")
                
        except Exception as queue_err:
            logger.error(f"❌ Failed to queue contract generation: {queue_err}")
            # Continue without queuing - form submission still succeeds
    
    # Queue email notifications as background job (don't block response)
    try:
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)
        
        # Queue email notification job
        await pool.enqueue_job(
            'send_form_notification_emails_task',
            client.id,
            user.id,
            data.ownerUid
        )
        logger.info(f"📧 Email notification job queued for client {client.id}")
            
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to queue email notifications: {email_err}")
        # Continue - email failure shouldn't fail the submission
    
    return PublicSubmitResponse(
        client=ClientResponse(
            id=client.id,
            public_id=client.public_id,
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
        contractPdfUrl=None,  # Will be available via job status endpoint
        jobId=job_id,
        message="Form submitted successfully - Contract generation in progress" if job_id else "Form submitted successfully"
    )


class SignContractRequest(BaseModel):
    clientPublicId: str  # UUID for secure public access
    contractPublicId: Optional[str] = None  # UUID for specific contract (optional for backwards compatibility)
    signature: str


# Rate limiter for contract signing - 10 per hour per IP
rate_limit_sign_contract = create_rate_limiter(
    limit=10,
    window_seconds=3600,
    key_prefix="sign_contract",
    use_ip=True
)


@router.post("/public/sign-contract")
async def sign_contract(
    data: SignContractRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_sign_contract)
):
    """
    Public endpoint for clients to sign their contract after reviewing the PDF.
    Updates the contract with the client's signature and audit trail.
    Rate limited to 10 per hour per IP.
    Uses UUID for secure access (prevents enumeration).
    """
    import hashlib
    from datetime import datetime
    from ..models import Contract
    from .contracts_pdf import generate_contract_html, html_to_pdf
    from .upload import get_r2_client, generate_presigned_url, R2_BUCKET_NAME
    from ..email_service import send_contract_signed_notification

    # Validate UUID format
    if not validate_uuid(data.clientPublicId):
        raise HTTPException(status_code=400, detail="Invalid client identifier")

    # Validate signature size (prevent DOS with huge base64 strings)
    if len(data.signature) > 500000:  # ~375KB decoded
        raise HTTPException(status_code=400, detail="Signature data too large")

    # Capture signature audit data
    client_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else "unknown"
    )
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "unknown")

    logger.info(f"📝 Contract signing request for client public_id: {data.clientPublicId}")

    # Find the client by public_id
    client = db.query(Client).filter(Client.public_id == data.clientPublicId).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Find the contract for this client
    if data.contractPublicId:
        # Find specific contract by public_id
        contract = (
            db.query(Contract)
            .filter(Contract.client_id == client.id, Contract.public_id == data.contractPublicId)
            .first()
        )
    else:
        # Fallback: get most recent contract for backwards compatibility
        contract = (
            db.query(Contract)
            .filter(Contract.client_id == client.id)
            .order_by(Contract.created_at.desc())
            .first()
        )
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
    
    # Update client status from "pending_signature" to "new_lead"
    # Now the client will appear in the provider's client list
    if client.status == "pending_signature":
        client.status = "new_lead"
        logger.info(f"✅ Client status updated from pending_signature to new_lead: client_id={client.id}")
    
    # Queue PDF regeneration as background job (don't block the response!)
    logger.info(f"📄 Queueing PDF regeneration for contract {contract.id}")
    try:
        from arq import create_pool
        from ..worker import get_redis_settings
        
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)
        
        job = await pool.enqueue_job(
            'regenerate_contract_pdf_task',
            contract.id
        )
        
        logger.info(f"✅ PDF regeneration queued: job_id={job.job_id}")
    except Exception as queue_err:
        logger.error(f"⚠️ Failed to queue PDF regeneration: {queue_err}")
        # Don't fail the signature if queueing fails
    
    db.commit()
    db.refresh(contract)
    
    logger.info(f"✅ Contract signed by client: contract_id={contract.id}")
    
    # Send notification to business owner (async, don't block)
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"
        
        if user.email:
            # Fire and forget - don't await
            import asyncio
            asyncio.create_task(
                send_contract_signed_notification(
                to=user.email,
                business_name=business_name,
                client_name=client.contact_name or client.business_name,
                contract_title=contract.title,
                )
            )
            logger.info(f"📧 Contract signed notification queued for: {user.email}")
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to send contract signed notification: {email_err}")
    
    # Return immediately - PDF is being generated in background
    return {
        "success": True,
        "message": "Contract signed successfully. PDF is being generated.",
        "contract_id": contract.id,
        "contract_public_id": str(contract.public_id)
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
