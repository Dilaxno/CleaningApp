import csv
import logging
import re
import uuid
from datetime import datetime
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..auth import get_current_user
from ..database import get_db
from ..models import BusinessConfig, Client, Contract, Schedule, User
from ..rate_limiter import create_rate_limiter
from ..utils.sanitization import sanitize_string

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
    use_ip=True,
)

rate_limit_form_global = create_rate_limiter(
    limit=15,
    window_seconds=60,  # 15 submissions per minute globally
    key_prefix="form_submit_global",
    use_ip=False,
)


def validate_us_phone(phone: str) -> str:
    """Validate and normalize US phone number"""
    if not phone:
        return phone

    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    # Handle +1 prefix
    if digits.startswith("1") and len(digits) == 11:
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

    @field_validator("phone")
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

    @field_validator("phone")
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
    created_at: Optional[datetime] = None
    form_data: Optional[dict] = None  # Include form_data for detailed view

    class Config:
        from_attributes = True


@router.get("", response_model=list[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all clients for the current user (excludes pending_signature clients)"""
    # Filter out clients with "pending_signature" status - they haven't signed the contract yet
    clients = (
        db.query(Client)
        .filter(Client.user_id == current_user.id, Client.status != "pending_signature")
        .order_by(Client.created_at.desc())
        .all()
    )
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
            notes=c.notes,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.get("/export")
async def export_clients_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Export clients as CSV with optional filters.

    Requires authentication via Bearer token in Authorization header.
    """
    try:
        logger.info(f"📊 CSV Export requested by user {current_user.id} ({current_user.email})")

        # Base query - exclude pending_signature clients
        query = db.query(Client).filter(
            Client.user_id == current_user.id, Client.status != "pending_signature"
        )

        # Apply status filter
        if status and status != "all":
            query = query.filter(Client.status == status)
            logger.info(f"  Filter: status={status}")

        # Apply search filter (by name or email)
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                (Client.business_name.ilike(search_term))
                | (Client.contact_name.ilike(search_term))
                | (Client.email.ilike(search_term))
            )
            logger.info(f"  Filter: search={search}")

        # Apply date range filter
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(Client.created_at >= start_dt)
                logger.info(f"  Filter: start_date={start_date}")
            except ValueError as e:
                logger.warning(f"  Invalid start_date format: {start_date} - {e}")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(Client.created_at <= end_dt)
                logger.info(f"  Filter: end_date={end_date}")
            except ValueError as e:
                logger.warning(f"  Invalid end_date format: {end_date} - {e}")

        # Get filtered clients
        clients = query.order_by(Client.created_at.desc()).all()
        logger.info(f"  Found {len(clients)} clients to export")

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "ID",
                "Business Name",
                "Contact Name",
                "Email",
                "Phone",
                "Property Type",
                "Property Size (sq ft)",
                "Frequency",
                "Status",
                "Notes",
                "Created At",
            ]
        )

        # Write data
        for client in clients:
            writer.writerow(
                [
                    client.id,
                    client.business_name or "",
                    client.contact_name or "",
                    client.email or "",
                    client.phone or "",
                    client.property_type or "",
                    client.property_size or "",
                    client.frequency or "",
                    client.status or "",
                    client.notes or "",
                    client.created_at.strftime("%Y-%m-%d %H:%M:%S") if client.created_at else "",
                ]
            )

        # Prepare response
        output.seek(0)
        filename = f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        logger.info(f"✅ CSV export successful: {filename} ({len(clients)} clients)")

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache",
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like auth errors)
        raise
    except Exception as e:
        logger.error(f"❌ CSV export failed for user {current_user.id}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Failed to export clients. Please try again.")


# ============================================================================
# QUOTE REQUESTS ROUTES
# IMPORTANT: These must come BEFORE /{client_id} route to avoid path conflicts
# ============================================================================

@router.get("/quote-requests/stats/summary")
async def get_quote_requests_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get summary statistics for quote requests.
    """
    # Count by status
    pending_count = db.query(func.count(Client.id)).filter(
        Client.user_id == current_user.id,
        Client.quote_status == "pending_review"
    ).scalar()

    approved_count = db.query(func.count(Client.id)).filter(
        Client.user_id == current_user.id,
        Client.quote_status == "approved"
    ).scalar()

    adjusted_count = db.query(func.count(Client.id)).filter(
        Client.user_id == current_user.id,
        Client.quote_status == "adjusted"
    ).scalar()

    rejected_count = db.query(func.count(Client.id)).filter(
        Client.user_id == current_user.id,
        Client.quote_status == "rejected"
    ).scalar()

    # Total quote value pending
    total_pending_value = db.query(func.sum(Client.original_quote_amount)).filter(
        Client.user_id == current_user.id,
        Client.quote_status == "pending_review"
    ).scalar() or 0

    return {
        "pending_count": pending_count,
        "approved_count": approved_count,
        "adjusted_count": adjusted_count,
        "rejected_count": rejected_count,
        "total_pending_value": float(total_pending_value),
    }


@router.get("/quote-requests")
async def get_quote_requests(
    status: Optional[str] = Query(None, description="Filter by quote status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all quote requests for the provider dashboard.
    Returns clients with quote_status = 'pending_review' or other specified status.
    """
    query = db.query(Client).filter(Client.user_id == current_user.id)

    # Filter by status if provided
    if status:
        query = query.filter(Client.quote_status == status)
    else:
        # Default to pending review
        query = query.filter(Client.quote_status == "pending_review")

    # Order by most recent first
    query = query.order_by(Client.quote_submitted_at.desc())

    clients = query.all()

    # Format response
    quote_requests = []
    for client in clients:
        quote_requests.append({
            "id": client.id,
            "public_id": client.public_id,
            "business_name": client.business_name,
            "contact_name": client.contact_name,
            "email": client.email,
            "phone": client.phone,
            "property_type": client.property_type,
            "property_size": client.property_size,
            "frequency": client.frequency,
            "quote_status": client.quote_status,
            "quote_submitted_at": client.quote_submitted_at.isoformat() if client.quote_submitted_at else None,
            "quote_approved_at": client.quote_approved_at.isoformat() if client.quote_approved_at else None,
            "original_quote_amount": client.original_quote_amount,
            "adjusted_quote_amount": client.adjusted_quote_amount,
            "quote_adjustment_notes": client.quote_adjustment_notes,
            "form_data": client.form_data,
            "created_at": client.created_at.isoformat() if client.created_at else None,
        })

    return {
        "quote_requests": quote_requests,
        "total": len(quote_requests),
    }


@router.get("/quote-requests/{client_id}")
async def get_quote_request_detail(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific quote request.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Quote request not found")

    # Get quote history if available
    from ..models import QuoteHistory
    history = db.query(QuoteHistory).filter(
        QuoteHistory.client_id == client_id
    ).order_by(QuoteHistory.created_at.desc()).all()

    history_entries = []
    for entry in history:
        history_entries.append({
            "id": entry.id,
            "action": entry.action,
            "amount": entry.amount,
            "notes": entry.notes,
            "created_by": entry.created_by,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        })

    return {
        "id": client.id,
        "public_id": client.public_id,
        "business_name": client.business_name,
        "contact_name": client.contact_name,
        "email": client.email,
        "phone": client.phone,
        "property_type": client.property_type,
        "property_size": client.property_size,
        "frequency": client.frequency,
        "status": client.status,
        "quote_status": client.quote_status,
        "quote_submitted_at": client.quote_submitted_at.isoformat() if client.quote_submitted_at else None,
        "quote_approved_at": client.quote_approved_at.isoformat() if client.quote_approved_at else None,
        "quote_approved_by": client.quote_approved_by,
        "original_quote_amount": client.original_quote_amount,
        "adjusted_quote_amount": client.adjusted_quote_amount,
        "quote_adjustment_notes": client.quote_adjustment_notes,
        "form_data": client.form_data,
        "notes": client.notes,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
        "history": history_entries,
    }


class BatchDeleteQuoteRequestsRequest(BaseModel):
    quoteRequestIds: list[int]


@router.post("/quote-requests/batch-delete")
async def batch_delete_quote_requests(
    data: BatchDeleteQuoteRequestsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Batch delete multiple quote requests (clients with quote_status).
    Only deletes clients that belong to the current user.
    """
    if not data.quoteRequestIds:
        raise HTTPException(status_code=400, detail="No quote request IDs provided")

    deleted_count = 0

    for client_id in data.quoteRequestIds:
        client = (
            db.query(Client)
            .filter(
                Client.id == client_id,
                Client.user_id == current_user.id
            )
            .first()
        )
        
        if client:
            # Delete the client (cascades to quote_history, contracts, schedules, etc.)
            db.delete(client)
            deleted_count += 1

    db.commit()

    logger.info(f"✅ User {current_user.id} deleted {deleted_count} quote requests")

    return {
        "message": f"Successfully deleted {deleted_count} quote request(s)",
        "deletedCount": deleted_count,
    }


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific client with detailed information including form_data"""
    client = (
        db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    )

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
        created_at=client.created_at,
        form_data=client.form_data,
    )


@router.post("", response_model=ClientResponse)
async def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        status="new_lead",
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    # Note: Client count is incremented when contract is fully signed (both parties)
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
        notes=client.notes,
        created_at=client.created_at,
    )


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a client"""
    client = (
        db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    )
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
        notes=client.notes,
        created_at=client.created_at,
    )


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a client"""
    from ..plan_limits import decrement_client_count

    client = (
        db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check if client has signed the contract (client signature exists)
    # Client count is incremented when client signs, so we decrement if they signed
    has_signed_contract = any(
        c.client_signature or c.client_signature_timestamp for c in client.contracts
    )

    db.delete(client)
    db.commit()

    # Decrement client count if they had signed the contract
    if has_signed_contract:
        decrement_client_count(current_user, db)
    return {"message": "Client deleted"}


class BatchDeleteRequest(BaseModel):
    clientIds: list[int]


@router.post("/batch-delete")
async def batch_delete_clients(
    data: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch delete multiple clients"""
    from ..models_invoice import Invoice
    from ..plan_limits import decrement_client_count

    if not data.clientIds:
        raise HTTPException(status_code=400, detail="No client IDs provided")

    # Verify all clients belong to the current user and delete them
    deleted_count = 0
    signed_clients_count = 0

    for client_id in data.clientIds:
        client = (
            db.query(Client)
            .filter(Client.id == client_id, Client.user_id == current_user.id)
            .first()
        )
        if client:
            # Check if client has signed the contract (client signature exists)
            has_signed_contract = any(
                c.client_signature or c.client_signature_timestamp for c in client.contracts
            )
            if has_signed_contract:
                signed_clients_count += 1

            # Get contract IDs for this client
            contract_ids = [c.id for c in client.contracts]

            # Delete invoices linked to these contracts first (FK constraint)
            if contract_ids:
                db.query(Invoice).filter(Invoice.contract_id.in_(contract_ids)).delete(
                    synchronize_session=False
                )

            db.delete(client)
            deleted_count += 1

    db.commit()

    # Decrement client count for each deleted client that had signed
    for _ in range(signed_clients_count):
        decrement_client_count(current_user, db)

    return {
        "message": f"Successfully deleted {deleted_count} client(s)",
        "deletedCount": deleted_count,
    }


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
    quoteStatus: Optional[str] = None  # Quote approval status: pending_review, approved, etc.
    createOnly: Optional[bool] = False  # NEW: Only create client, don't generate contract yet

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            return validate_us_phone(v)
        return v


class QuotePreviewRequest(BaseModel):
    """Schema for quote preview - calculates quote without creating client"""

    ownerUid: str
    formData: dict


class AddonDetail(BaseModel):
    """Schema for addon detail in quote"""

    name: str
    quantity: int
    unitPrice: float
    totalPrice: float
    pricingMetric: str


class QuotePreviewResponse(BaseModel):
    """Response for quote preview"""

    basePrice: float
    discountPercent: float
    discountAmount: float
    firstCleaningDiscountType: Optional[str] = None
    firstCleaningDiscountValue: Optional[float] = None
    firstCleaningDiscountAmount: Optional[float] = 0
    addonAmount: float = 0
    addonDetails: list[AddonDetail] = []
    finalPrice: float
    estimatedHours: float
    cleaners: int
    pricingModel: str
    frequency: str
    pricingExplanation: str
    quotePending: bool = False
    selectedPackage: Optional[dict] = None


class PublicSubmitResponse(BaseModel):
    client: Optional[ClientResponse] = None
    contractPdfUrl: Optional[str] = None
    jobId: Optional[str] = None
    message: str


@router.post("/public/quote-preview", response_model=QuotePreviewResponse)
async def get_quote_preview(
    data: QuotePreviewRequest, request: Request, db: Session = Depends(get_db)
):
    """
    Public endpoint to calculate and preview quote before form submission.
    No client is created - just returns the calculated quote with explanation.
    Supports custom domain validation for security.
    """
    from .contracts_pdf import calculate_quote

    client_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else "unknown"
    )
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    # Custom domain security validation
    if hasattr(request.state, "is_custom_domain") and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (
            not hasattr(request.state, "custom_domain_user_uid")
            or request.state.custom_domain_user_uid != data.ownerUid
        ):
            logger.warning(
                f"🚫 Custom domain security violation in quote preview: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match form owner {data.ownerUid} from IP {client_ip}"
            )
            raise HTTPException(
                status_code=403, detail="Access denied: Custom domain does not match form owner"
            )
        logger.info(f"✅ Custom domain validation passed for quote preview {data.ownerUid}")

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
            quotePending=True,
        )

    # Check if this IP has any signed contracts with this business (first cleaning detection)
    existing_signed_contract = (
        db.query(Contract)
        .filter(
            Contract.user_id == user.id,
            Contract.client_signature_ip == client_ip,
            Contract.client_signature.isnot(None),
        )
        .first()
    )

    # Auto-set isFirstCleaning based on IP - if no signed contracts from this IP, it's their first cleaning
    # BUT: If frontend explicitly sent isFirstCleaning=true (for quote preview), respect that
    frontend_is_first = data.formData.get("isFirstCleaning", None)
    is_first_cleaning_by_ip = existing_signed_contract is None

    # Use frontend value if provided, otherwise use IP-based detection
    if frontend_is_first is not None:
        is_first_cleaning = bool(frontend_is_first)
        logger.info(
            f"🔍 Using frontend isFirstCleaning value: {is_first_cleaning} (IP check would be: {is_first_cleaning_by_ip})"
        )
    else:
        is_first_cleaning = is_first_cleaning_by_ip

    # Log formData keys for debugging
    logger.info(
        f"📦 Quote preview - FormData keys: {list(data.formData.keys())}, selectedPackage: {data.formData.get('selectedPackage')}"
    )
    logger.info(
        f"🔍 Using IP-based first cleaning check for IP {client_ip}: {is_first_cleaning} (existing signed contracts: {'none' if is_first_cleaning else 'found'})"
    )

    data.formData["isFirstCleaning"] = is_first_cleaning

    # Calculate quote
    quote = calculate_quote(config, data.formData)

    # Log the discount calculation for debugging
    logger.info(
        f"📊 Quote calculation - first_cleaning_discount_amount: ${quote.get('first_cleaning_discount_amount', 0):.2f}, "
        f"first_cleaning_discount_type: {quote.get('first_cleaning_discount_type')}, "
        f"first_cleaning_discount_value: {quote.get('first_cleaning_discount_value')}, "
        f"isFirstCleaning: {is_first_cleaning}"
    )

    # Convert addon details from snake_case to camelCase for API response
    addon_details_camel = [
        AddonDetail(
            name=addon["name"],
            quantity=addon["quantity"],
            unitPrice=addon["unit_price"],
            totalPrice=addon["total_price"],
            pricingMetric=addon["pricing_metric"],
        )
        for addon in quote.get("addon_details", [])
    ]

    # Build pricing explanation
    pricing_model = config.pricing_model or ""
    property_size = int(data.formData.get("squareFootage", 0) or 0)
    # num_rooms reserved for future pricing calculations
    frequency = data.formData.get("cleaningFrequency", "")

    explanation_parts = []

    business_name = config.business_name or "This business"

    if quote.get("quote_pending"):
        explanation = (
            "Quote will be provided by the service provider after reviewing your requirements."
        )
    else:
        # Base rate explanation - show business name and rate per metric with calculation
        if pricing_model == "sqft" and config.rate_per_sqft and property_size > 0:
            base_calculation = property_size * config.rate_per_sqft
            explanation_parts.append(
                f"{business_name} charges ${config.rate_per_sqft:.2f} per sq ft ({property_size:,} sq ft × ${config.rate_per_sqft:.2f} = ${base_calculation:,.2f})"
            )
        elif pricing_model == "hourly" and config.hourly_rate:
            estimated_hours = quote.get("estimated_hours", 0)
            if estimated_hours > 0:
                # Determine number of cleaners based on property size
                num_cleaners = config.cleaners_small_job or 1
                if property_size > 2000:
                    num_cleaners = config.cleaners_large_job or 2
                
                # Generate explanation based on hourly rate mode
                if config.hourly_rate_mode == "general":
                    # General hourly rate: Total = Hourly Rate × Job Duration
                    base_calculation = estimated_hours * config.hourly_rate
                    explanation_parts.append(
                        f"{business_name} charges ${config.hourly_rate:.2f} per hour ({estimated_hours:.1f} hours × ${config.hourly_rate:.2f} = ${base_calculation:,.2f})"
                    )
                else:
                    # Per cleaner mode: Total = Hourly Rate × Number of Cleaners × Job Duration
                    base_calculation = estimated_hours * config.hourly_rate * num_cleaners
                    explanation_parts.append(
                        f"{business_name} charges ${config.hourly_rate:.2f} per hour per cleaner ({estimated_hours:.1f} hours × ${config.hourly_rate:.2f} × {num_cleaners} cleaners = ${base_calculation:,.2f})"
                    )
            else:
                # No estimated hours available
                if config.hourly_rate_mode == "general":
                    explanation_parts.append(
                        f"{business_name} charges ${config.hourly_rate:.2f} per hour"
                    )
                else:
                    explanation_parts.append(
                        f"{business_name} charges ${config.hourly_rate:.2f} per hour per cleaner"
                    )
        elif pricing_model == "packages":
            # Find the selected package for explanation
            selected_package_id = data.formData.get("selectedPackage")
            selected_package = None
            if selected_package_id and config.custom_packages:
                for package in config.custom_packages:
                    if package.get("id") == selected_package_id:
                        selected_package = package
                        break

            if selected_package:
                package_name = selected_package.get("name", "Selected package")
                price_type = selected_package.get("priceType", "flat")

                if price_type == "flat" and selected_package.get("price"):
                    explanation_parts.append(
                        f"{package_name} package: ${selected_package['price']:,.2f}"
                    )
                elif price_type == "range":
                    price_min = selected_package.get("priceMin", 0)
                    price_max = selected_package.get("priceMax", 0)
                    if price_min and price_max:
                        explanation_parts.append(
                            f"{package_name} package: ${price_min:,.2f} - ${price_max:,.2f}"
                        )
                    else:
                        explanation_parts.append(f"{package_name} package selected")
                else:
                    explanation_parts.append(f"{package_name} package - quote required")

                # Add duration info if available
                if selected_package.get("duration"):
                    duration_hours = selected_package["duration"] / 60.0
                    explanation_parts.append(f"Estimated duration: {duration_hours:.1f} hours")
            else:
                explanation_parts.append("Custom service package selected")
        elif pricing_model == "flat":
            if config.flat_rate:
                explanation_parts.append(
                    f"{business_name} charges a flat rate of ${config.flat_rate:,.2f} per service"
                )
            elif config.flat_rate_small or config.flat_rate_medium or config.flat_rate_large:
                # Tiered flat rate - determine which tier applies
                if property_size > 0:
                    if property_size <= 1500 and config.flat_rate_small:
                        explanation_parts.append(
                            f"{business_name} charges ${config.flat_rate_small:,.2f} for small properties (up to 1,500 sq ft)"
                        )
                    elif property_size <= 3000 and config.flat_rate_medium:
                        explanation_parts.append(
                            f"{business_name} charges ${config.flat_rate_medium:,.2f} for medium properties (1,501-3,000 sq ft)"
                        )
                    elif config.flat_rate_large:
                        explanation_parts.append(
                            f"{business_name} charges ${config.flat_rate_large:,.2f} for large properties (3,000+ sq ft)"
                        )
                else:
                    explanation_parts.append(f"{business_name} uses tiered flat rate pricing")
            else:
                explanation_parts.append(
                    f"{business_name} charges a flat rate of ${config.flat_rate:,.2f}"
                )
        else:
            explanation_parts.append(f"Base service rate: ${quote['base_price']:,.2f}")

        # Discount explanation
        if quote["discount_percent"] > 0:
            explanation_parts.append(
                f"{quote['discount_percent']:.0f}% {frequency.lower()} frequency discount applied"
            )

        explanation = " • ".join(explanation_parts)

    return QuotePreviewResponse(
        basePrice=quote["base_price"],
        discountPercent=quote["discount_percent"],
        discountAmount=quote["discount_amount"],
        firstCleaningDiscountType=quote.get("first_cleaning_discount_type"),
        firstCleaningDiscountValue=quote.get("first_cleaning_discount_value"),
        firstCleaningDiscountAmount=quote.get("first_cleaning_discount_amount", 0),
        addonAmount=quote.get("addon_amount", 0),
        addonDetails=addon_details_camel,
        finalPrice=quote["final_price"],
        estimatedHours=quote["estimated_hours"],
        cleaners=quote["cleaners"],
        pricingModel=pricing_model,
        frequency=frequency,
        pricingExplanation=explanation,
        quotePending=quote.get("quote_pending", False),
        selectedPackage=quote.get("selected_package"),
    )


@router.post("/public/submit")
async def submit_public_form(
    data: PublicClientCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _ip: None = Depends(rate_limit_form_per_ip),
    _global: None = Depends(rate_limit_form_global),
):
    """
    Public endpoint for clients to submit intake forms.
    Rate limited: 5 per minute per IP, 15 per minute globally.
    Contract generation is queued asynchronously to prevent timeouts.
    No authentication required - this is accessed via shareable link.
    Supports custom domain validation for security.
    """
    from arq import create_pool

    from ..worker import get_redis_settings

    # Capture client info
    client_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else "unknown"
    )
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    # User agent available for future analytics/logging

    logger.info(f"📥 Public form submission for owner UID: {data.ownerUid} from IP: {client_ip}")

    # Custom domain security validation
    if hasattr(request.state, "is_custom_domain") and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (
            not hasattr(request.state, "custom_domain_user_uid")
            or request.state.custom_domain_user_uid != data.ownerUid
        ):
            logger.warning(
                f"🚫 Custom domain security violation: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match form owner {data.ownerUid} from IP {client_ip}"
            )
            raise HTTPException(
                status_code=403, detail="Access denied: Custom domain does not match form owner"
            )
        logger.info(f"✅ Custom domain validation passed for {data.ownerUid}")

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
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, data.email):
            validation_errors.append("Invalid email format")
        elif len(data.email) > 255:
            validation_errors.append("Email must be less than 255 characters")

    # Validate phone format if provided
    if data.phone:
        # Remove all non-digit characters for validation
        phone_digits = re.sub(r"\D", "", data.phone)
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
            detail={"message": "Validation failed", "errors": validation_errors},
        )

    # Find the user by Firebase UID (with business_config for business name)
    user = (
        db.query(User)
        .filter(User.firebase_uid == data.ownerUid)
        .options(joinedload(User.business_config))
        .first()
    )
    if not user:
        logger.error(f"❌ User not found for Firebase UID: {data.ownerUid}")
        raise HTTPException(status_code=404, detail="Business not found")

    # Check if this IP has any signed contracts with this business (first cleaning detection)
    existing_signed_contract = (
        db.query(Contract)
        .filter(
            Contract.user_id == user.id,
            Contract.client_signature_ip == client_ip,
            Contract.client_signature.isnot(None),
        )
        .first()
    )

    # Auto-set isFirstCleaning based on IP - if no signed contracts from this IP, it's their first cleaning
    is_first_cleaning = existing_signed_contract is None
    if data.formData:
        data.formData["isFirstCleaning"] = is_first_cleaning
        # Log selectedPackage for debugging
        logger.info(
            f"📦 FormData keys: {list(data.formData.keys())}, selectedPackage: {data.formData.get('selectedPackage')}"
        )

    logger.info(
        f"🔍 First cleaning check for IP {client_ip}: {is_first_cleaning} (existing signed contracts: {'none' if is_first_cleaning else 'found'})"
    )

    # Extract frequency from formData if not provided directly
    frequency = data.frequency
    if not frequency and data.formData:
        frequency = data.formData.get("cleaningFrequency")

    # If still no frequency, infer from property type (e.g., move-in-out is always one-time)
    if not frequency and data.propertyType:
        property_type_lower = data.propertyType.lower()
        if "move" in property_type_lower:
            frequency = "One-time"
        elif "construction" in property_type_lower or "post-construction" in property_type_lower:
            frequency = "One-time"
        elif "event" in property_type_lower:
            frequency = "One-time"

    # Calculate quote amount if formData is provided
    quote_amount = None
    if data.formData:
        try:
            from .contracts_pdf import calculate_quote
            # Get business config for quote calculation
            if user.business_config:
                logger.info(f"📊 Calculating quote for {data.businessName} with formData keys: {list(data.formData.keys())}")
                quote_result = calculate_quote(user.business_config, data.formData)
                quote_amount = quote_result.get("final_price", 0)  # Use final_price from calculate_quote
                logger.info(f"💰 Quote calculation result: {quote_result}")
                logger.info(f"💰 Final quote amount: ${quote_amount} for client {data.businessName}")
                
                # If quote is 0 or None, check if it's a quote_pending situation
                if not quote_amount or quote_amount == 0:
                    if quote_result.get("quote_pending"):
                        logger.warning(f"⚠️ Quote is pending manual review for {data.businessName}")
                    else:
                        logger.warning(f"⚠️ Quote amount is 0 but not marked as pending. Quote result: {quote_result}")
            else:
                logger.warning(f"⚠️ No business config found for user {user.id}")
        except Exception as e:
            logger.error(f"❌ Failed to calculate quote amount: {e}")
            logger.exception(e)

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
        status="pending_signature",  # Will change to "new_lead" after contract is signed
        quote_status=data.quoteStatus or "pending_review",  # Set quote status
        quote_submitted_at=func.now() if data.quoteAccepted else None,  # Track when client approved
        original_quote_amount=quote_amount if quote_amount and quote_amount > 0 else None,  # Store original automated quote (None if 0 or not calculated)
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    # Create quote history entry if quote was accepted
    if data.quoteAccepted and quote_amount:
        from .models import QuoteHistory
        quote_history_entry = QuoteHistory(
            client_id=client.id,
            action="submitted",
            amount=quote_amount,
            notes="Client approved automated quote",
            created_by=f"client:{data.email or 'unknown'}",
        )
        db.add(quote_history_entry)
        db.commit()

    # Send emails if quote was accepted
    if data.quoteAccepted and data.email:
        from ..email_service import send_quote_submitted_confirmation, send_quote_review_notification
        
        # Get business name from business_config
        business_name = (
            user.business_config.business_name 
            if user.business_config and user.business_config.business_name 
            else "Service Provider"
        )
        
        # Send confirmation email to client (background task)
        background_tasks.add_task(
            send_quote_submitted_confirmation,
            to=data.email,
            client_name=data.contactName or data.businessName,
            business_name=business_name,
            quote_amount=quote_amount or 0,
        )
        
        # Send notification email to provider (background task)
        if user.email:
            background_tasks.add_task(
                send_quote_review_notification,
                to=user.email,
                provider_name=business_name,
                client_name=data.contactName or data.businessName,
                client_email=data.email,
                quote_amount=quote_amount or 0,
                client_id=client.id,
                client_public_id=client.public_id,
            )

    # If createOnly flag is set, skip contract generation and return client data immediately
    if data.createOnly:
        logger.info(
            f"✅ Client created (ID: {client.id}) - skipping contract generation (createOnly=True)"
        )
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
                notes=client.notes,
                created_at=client.created_at,
            ),
            contractPdfUrl=None,
            jobId=None,
            message="Client created successfully - ready for scheduling",
        )

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
                    "generate_contract_pdf_task",
                    client.id,
                    data.ownerUid,
                    data.formData,
                    data.clientSignature,
                )

                job_id = job.job_id
                logger.info(f"📋 Contract generation job queued: {job_id}")
            else:
                logger.warning(
                    f"⚠️ No business config found for user {user.id} - skipping contract generation"
                )

        except Exception as queue_err:
            logger.error(f"❌ Failed to queue contract generation: {queue_err}")
            # Continue without queuing - form submission still succeeds

    # Queue email notifications as background job (don't block response)
    try:
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)

        # Queue email notification job
        await pool.enqueue_job(
            "send_form_notification_emails_task", client.id, user.id, data.ownerUid
        )
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to queue email notifications: {email_err}")
        # Continue - email failure shouldn't fail the submission

    # Determine response message based on request type
    if job_id:
        response_message = "Form submitted successfully - Contract generation in progress"
    else:
        response_message = "Form submitted successfully"

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
            notes=client.notes,
            created_at=client.created_at,
        ),
        contractPdfUrl=None,  # Will be available via job status endpoint
        jobId=job_id,
        message=response_message,
    )


class SignContractRequest(BaseModel):
    clientPublicId: str  # UUID for secure public access
    contractPublicId: Optional[str] = (
        None  # UUID for specific contract (optional for backwards compatibility)
    )
    signature: str
    customQuoteRequestId: Optional[int] = None  # Link to custom quote request if applicable


class GenerateContractRequest(BaseModel):
    """Schema for generating contract for existing client"""

    formData: dict


# Rate limiter for contract signing - 10 per hour per IP
rate_limit_sign_contract = create_rate_limiter(
    limit=10, window_seconds=3600, key_prefix="sign_contract", use_ip=True
)


@router.post("/{client_id}/generate-contract")
async def generate_contract_for_client(
    client_id: int,
    data: GenerateContractRequest,
    db: Session = Depends(get_db),
):
    """
    Public endpoint to generate a contract for an existing client.
    Used in the new flow: create client → schedule → generate contract → sign.
    No authentication required - accessed via public form flow.
    """
    from arq import create_pool

    from ..worker import get_redis_settings

    logger.info(f"📋 Generating contract for client ID: {client_id}")

    # Find the client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.error(f"❌ Client not found: {client_id}")
        raise HTTPException(status_code=404, detail="Client not found")

    # Get the user/business owner
    user = db.query(User).filter(User.id == client.user_id).first()
    if not user:
        logger.error(f"❌ User not found for client: {client_id}")
        raise HTTPException(status_code=404, detail="Business not found")

    # Get business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        logger.warning(f"⚠️ No business config found for user {user.id}")
        raise HTTPException(status_code=404, detail="Business configuration not found")

    # Update client's form_data if provided
    if data.formData:
        client.form_data = data.formData
        db.commit()
        db.refresh(client)

    try:
        # Enqueue contract generation job
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)

        job = await pool.enqueue_job(
            "generate_contract_pdf_task",
            client.id,
            user.firebase_uid,
            data.formData,
            None,  # No signature yet - client will sign after reviewing
        )

        job_id = job.job_id
        logger.info(f"📋 Contract generation job queued: {job_id} for client {client_id}")

        return {
            "message": "Contract generation started",
            "jobId": job_id,
            "clientId": client.id,
        }

    except Exception as e:
        logger.error(f"❌ Failed to queue contract generation for client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start contract generation")


@router.get("/public/{client_public_id}/info")
async def get_client_info_by_public_id(
    client_public_id: str,
    db: Session = Depends(get_db),
):
    """
    Public endpoint to get client information by public_id.
    Used for quote-approved clients to check contract status and proceed to scheduling.
    Returns client_id, form_data, and contract_public_id if contract exists.
    """
    # Validate UUID format
    if not validate_uuid(client_public_id):
        raise HTTPException(status_code=400, detail="Invalid client identifier")

    # Find client by public_id
    client = db.query(Client).filter(Client.public_id == client_public_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get most recent contract if exists
    contract = (
        db.query(Contract)
        .filter(Contract.client_id == client.id)
        .order_by(Contract.created_at.desc())
        .first()
    )

    return {
        "client_id": client.id,
        "client_public_id": client.public_id,
        "business_name": client.business_name,
        "contact_name": client.contact_name,
        "email": client.email,
        "quote_status": client.quote_status,
        "form_data": client.form_data,
        "contract_public_id": contract.public_id if contract else None,
        "contract_id": contract.id if contract else None,
    }


@router.post("/public/sign-contract")
async def sign_contract(
    data: SignContractRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_sign_contract),
):
    """
    Public endpoint for clients to sign their contract after reviewing the PDF.
    Updates the contract with the client's signature and audit trail.
    Rate limited to 10 per hour per IP.
    Uses UUID for secure access (prevents enumeration).
    """
async def sign_contract(
    data: SignContractRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_sign_contract),
):
    """
    Public endpoint for clients to sign their contract after reviewing the PDF.
    Updates the contract with the client's signature and audit trail.
    Rate limited to 10 per hour per IP.
    Uses UUID for secure access (prevents enumeration).
    """
    import hashlib
    from datetime import datetime

    from ..email_service import (
        send_client_signature_confirmation,
        send_contract_signed_notification,
    )
    from ..models import Contract
    from .contracts_pdf import generate_contract_html, html_to_pdf
    from .upload import R2_BUCKET_NAME, generate_presigned_url, get_r2_client

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
    # Find the client by public_id
    client = db.query(Client).filter(Client.public_id == data.clientPublicId).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Find or create the contract for this client
    if data.contractPublicId:
        # Find specific contract by public_id
        contract = (
            db.query(Contract)
            .filter(
                Contract.client_id == client.id,
                Contract.public_id == data.contractPublicId,
            )
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

    # If no contract exists, create one from pending contract data
    if not contract:
        if not client.pending_contract_title:
            raise HTTPException(
                status_code=404, detail="No contract or pending contract data found"
            )

        # Create contract from pending data
        contract = Contract(
            user_id=client.user_id,
            client_id=client.id,
            title=client.pending_contract_title,
            description=client.pending_contract_description,
            contract_type=client.pending_contract_type,
            start_date=client.pending_contract_start_date,
            end_date=client.pending_contract_end_date,
            total_value=client.pending_contract_total_value,
            payment_terms=client.pending_contract_payment_terms,
            terms_conditions=client.pending_contract_terms_conditions,
            status="new",
        )
        db.add(contract)
        db.flush()  # Get the ID without committing

        # Clear pending contract data
        client.pending_contract_title = None
        client.pending_contract_description = None
        client.pending_contract_type = None
        client.pending_contract_start_date = None
        client.pending_contract_end_date = None
        client.pending_contract_total_value = None
        client.pending_contract_payment_terms = None
        client.pending_contract_terms_conditions = None

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

    # Update client onboarding status
    contract.client_onboarding_status = "pending_scheduling"

    # DO NOT update client status here - client should only appear in provider's list
    # after BOTH parties sign the contract (when provider signs)
    # Client status will be updated to "new_lead" when provider signs in contracts.py

    # Increment client count when client signs (commits to the service)
    # This counts the client for plan limits and statistics
    from ..plan_limits import increment_client_count

    increment_client_count(user, db)
    logger.info(f"✅ Client count incremented for user {user.id} after client signature")

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
                ContentType="image/png",
            )

            # Generate presigned URL (7 days max for R2)
            client_signature_url = generate_presigned_url(
                signature_key, expiration=604800
            )  # 7 days
        except Exception as sig_err:
            logger.warning(f"⚠️ Failed to upload client signature to R2: {sig_err}")

    # Regenerate PDF with client signature
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        if config and client.form_data:
            form_data = client.form_data
            old_pdf_key = contract.pdf_key
            # Calculate quote for regeneration
            from .contracts_pdf import calculate_quote

            quote = calculate_quote(config, form_data)

            # Get provider signature URL if exists
            provider_signature_url = None
            if contract.provider_signature and contract.provider_signature.startswith("data:image"):
                # Provider signature is base64, need to upload it too if not already done
                provider_signature_url = contract.provider_signature

            # Generate HTML with signature URLs - use contract's created_at for consistent dates
            html = await generate_contract_html(
                config,
                client,
                form_data,
                quote,
                db,
                client_signature=client_signature_url or data.signature,  # Use URL if available
                provider_signature=provider_signature_url,
                contract_created_at=contract.created_at,
                contract_public_id=contract.public_id,
            )

            # Verify signature URL is in HTML
            if client_signature_url and client_signature_url in html:
                pass  # Signature URL found
            elif data.signature in html:
                pass  # Signature data found
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
                    ContentType="application/pdf",
                )

                contract.pdf_key = pdf_key
                contract.pdf_hash = pdf_hash
                logger.info(f"📝 Updated contract.pdf_key from {old_pdf_key} to {pdf_key}")
            except Exception as upload_err:
                logger.warning(f"⚠️ Failed to upload signed PDF: {upload_err}")

    except Exception as pdf_err:
        logger.warning(f"⚠️ Failed to regenerate signed PDF: {pdf_err}")

    db.commit()
    db.refresh(contract)
    # Generate backend URL for the new signed PDF (avoids CORS issues)
    signed_pdf_url = None
    if contract.pdf_key:
        try:
            from ..config import FRONTEND_URL

            # Determine the backend base URL based on the frontend URL
            if "localhost" in FRONTEND_URL:
                backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace(
                    "localhost:5174", "localhost:8000"
                )
            else:
                backend_base = "https://api.cleanenroll.com"

            signed_pdf_url = f"{backend_base}/contracts/pdf/public/{contract.public_id}"
        except Exception as url_err:
            logger.warning(f"⚠️ Failed to generate backend URL: {url_err}")

    # Send notification to business owner
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"

        # Check notification preference before sending
        if user.email and user.notify_contract_signed:
            await send_contract_signed_notification(
                to=user.email,
                business_name=sanitize_string(business_name),
                client_name=sanitize_string(client.contact_name or client.business_name),
                contract_title=sanitize_string(contract.title),
            )
            logger.info(f"✅ Contract signed notification sent to {user.email}")
        elif user.email and not user.notify_contract_signed:
            logger.info("ℹ️ Contract signed notification skipped - user preference disabled")
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to send contract signed notification: {email_err}")

    # Send confirmation to client
    try:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"

        if client.email:
            await send_client_signature_confirmation(
                to=client.email,
                client_name=sanitize_string(client.contact_name or client.business_name),
                business_name=sanitize_string(business_name),
                contract_title=sanitize_string(contract.title),
                contract_pdf_url=signed_pdf_url,
            )
            logger.info(f"✅ Client signature confirmation sent to {client.email}")
    except Exception as email_err:
        logger.warning(f"⚠️ Failed to send client confirmation email: {email_err}")

    return {
        "success": True,
        "message": "Contract signed successfully. Awaiting service provider signature.",
        "signedPdfUrl": signed_pdf_url,
    }


class ScheduleDecisionRequest(BaseModel):
    action: str  # 'confirm' or 'request_change'
    proposed_start_time: Optional[str] = None
    proposed_end_time: Optional[str] = None


@router.post("/{client_id}/schedule-decision")
async def handle_schedule_decision(
    client_id: int, data: ScheduleDecisionRequest, db: Session = Depends(get_db)
):
    """
    Handle provider's decision on client's scheduled time
    Provider can confirm or propose a different time

    Automated email notifications:
    - Provider action (confirm/request_change): notify client AND provider.
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

        if data.action == "confirm":
            # Provider confirmed the client's selected time
            client.scheduling_status = "confirmed"
            db.commit()

            # Parse times once (also used for provider confirmation email)
            start_dt = None
            end_dt = None
            try:
                if client.scheduled_start_time:
                    start_dt = datetime.fromisoformat(
                        client.scheduled_start_time.replace("Z", "+00:00")
                    )
                if client.scheduled_end_time:
                    end_dt = datetime.fromisoformat(
                        client.scheduled_end_time.replace("Z", "+00:00")
                    )
            except Exception:
                # Keep emails resilient even if stored datetimes are malformed
                start_dt = None
                end_dt = None

            # Send confirmation email to client
            if client.email:
                content = f"""
                <p>Hi {client.contact_name or client.business_name},</p>
                <p>Great news! <strong>{business_name}</strong> has confirmed your preferred cleaning schedule.</p>
                <div style="background: #f0fdf4; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #22c55e;">
                  <p style="color: #15803d; font-weight: 600; margin-bottom: 12px;">✓ Confirmed Cleaning Date & Time</p>
                  <p style="color: #15803d; font-size: 16px; margin: 8px 0;">
                    📅 {(start_dt.strftime("%A, %B %d, %Y") if start_dt else "Confirmed")}
                  </p>
                  <p style="color: #15803d; font-size: 16px; margin: 8px 0;">
                    ⏰ {(start_dt.strftime("%I:%M %p") if start_dt else "")}{(" - " + end_dt.strftime("%I:%M %p")) if start_dt and end_dt else ""}
                  </p>
                </div>
                <p>Your first cleaning is all set! We look forward to serving you.</p>
                """

                await send_email(
                    to=client.email,
                    subject=f"Cleaning Schedule Confirmed - {business_name}",
                    title="Your Cleaning is Scheduled! 🎉",
                    content_html=content,
                )

            # Send confirmation email to provider (same action, other side)
            provider = db.query(User).filter(User.id == client.user_id).first()
            if provider and provider.email:
                provider_content = f"""
                <p>Hi {provider.full_name or business_name},</p>
                <p>You confirmed a cleaning schedule for <strong>{client.contact_name or client.business_name}</strong>.</p>
                <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                  <p style="margin:0; color:#334155; font-size: 14px;">
                    📅 {(start_dt.strftime("%A, %B %d, %Y") if start_dt else "Confirmed")}
                    {(start_dt.strftime("%I:%M %p") if start_dt else "")}{(" - " + end_dt.strftime("%I:%M %p")) if start_dt and end_dt else ""}
                  </p>
                </div>
                """
                await send_email(
                    to=provider.email,
                    subject=f"Schedule Confirmed for {client.contact_name or client.business_name}",
                    title="Schedule Confirmed",
                    content_html=provider_content,
                    is_user_email=True,
                )
        elif data.action == "request_change":
            # Provider requested a different time
            if not data.proposed_start_time or not data.proposed_end_time:
                raise HTTPException(status_code=400, detail="Proposed times are required")

            # Update scheduling status
            client.scheduling_status = "provider_requested_change"

            db.commit()

            # Parse original + proposed times once
            original_start = None
            original_end = None
            try:
                if client.scheduled_start_time:
                    original_start = datetime.fromisoformat(
                        client.scheduled_start_time.replace("Z", "+00:00")
                    )
                if client.scheduled_end_time:
                    original_end = datetime.fromisoformat(
                        client.scheduled_end_time.replace("Z", "+00:00")
                    )
            except Exception:
                original_start = None
                original_end = None

            proposed_start = datetime.fromisoformat(data.proposed_start_time.replace("Z", "+00:00"))
            proposed_end = datetime.fromisoformat(data.proposed_end_time.replace("Z", "+00:00"))

            # Send notification to client with provider's proposed time
            if client.email:
                content = f"""
                <p>Hi {client.contact_name or client.business_name},</p>
                <p><strong>{business_name}</strong> has reviewed your preferred cleaning schedule and would like to propose an alternative time that better fits their availability.</p>

                <div style="background: #fef3c7; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #f59e0b;">
                  <p style="color: #92400e; font-weight: 600; margin-bottom: 12px;">📅 Your Selected Time</p>
                  <p style="color: #92400e; font-size: 15px; margin: 8px 0;">
                    {(original_start.strftime("%A, %B %d, %Y") if original_start else "Selected")}
                  </p>
                  <p style="color: #92400e; font-size: 15px; margin: 8px 0;">
                    {(original_start.strftime("%I:%M %p") if original_start else "")}{(" - " + original_end.strftime("%I:%M %p")) if original_start and original_end else ""}
                  </p>
                </div>

                <div style="background: #dbeafe; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #3b82f6;">
                  <p style="color: #1e40af; font-weight: 600; margin-bottom: 12px;">✨ Provider's Proposed Time</p>
                  <p style="color: #1e40af; font-size: 16px; margin: 8px 0;">
                    📅 {proposed_start.strftime("%A, %B %d, %Y")}
                  </p>
                  <p style="color: #1e40af; font-size: 16px; margin: 8px 0;">
                    ⏰ {proposed_start.strftime("%I:%M %p")} - {proposed_end.strftime("%I:%M %p")}
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
                    content_html=content,
                )

            # Send confirmation email to provider (same action, other side)
            provider = db.query(User).filter(User.id == client.user_id).first()
            if provider and provider.email:
                provider_content = f"""
                <p>Hi {provider.full_name or business_name},</p>
                <p>You proposed an alternative time for <strong>{client.contact_name or client.business_name}</strong>.</p>

                <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                  <p style="margin:0; color:#334155; font-size: 14px;">
                    Proposed: {proposed_start.strftime("%A, %B %d, %Y")} {proposed_start.strftime("%I:%M %p")} - {proposed_end.strftime("%I:%M %p")}
                  </p>
                </div>
                """
                await send_email(
                    to=provider.email,
                    subject=f"Alternative Time Sent to {client.contact_name or client.business_name}",
                    title="Alternative Time Proposed",
                    content_html=provider_content,
                    is_user_email=True,
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        return {
            "success": True,
            "message": f"Schedule {data.action} processed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error handling schedule decision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ClientScheduleSubmission(BaseModel):
    scheduledDate: str  # YYYY-MM-DD format
    scheduledTime: str  # HH:MM format (24-hour)
    endTime: str  # HH:MM format (24-hour)
    durationMinutes: int


@router.post("/public/{client_id}/submit-schedule")
async def submit_client_schedule(
    client_id: int, data: ClientScheduleSubmission, db: Session = Depends(get_db)
):
    """
    Public endpoint for client to submit their preferred schedule time.
    This notifies the provider that the client has selected a time.
    No authentication required - accessed via public form flow.
    """
    from ..email_service import send_email

    try:
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get provider/user
        provider = db.query(User).filter(User.id == client.user_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Get business config for business name
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == client.user_id).first()
        business_name = config.business_name if config else "Your Business"

        # Parse and store the scheduled time
        try:
            # Combine date and time into ISO format datetime strings
            scheduled_start = f"{data.scheduledDate}T{data.scheduledTime}:00"
            scheduled_end = f"{data.scheduledDate}T{data.endTime}:00"

            # Parse datetime for duplicate check
            scheduled_datetime = datetime.fromisoformat(scheduled_start)

            # Check if schedule already exists to prevent duplicates
            # Use FOR UPDATE to lock the row and prevent race conditions
            existing_schedule = (
                db.query(Schedule)
                .filter(
                    Schedule.client_id == client.id,
                    Schedule.scheduled_date == scheduled_datetime.date(),
                    Schedule.start_time == data.scheduledTime,
                    Schedule.status == "scheduled",
                )
                .with_for_update()
                .first()
            )

            if existing_schedule:
                logger.warning(
                    f"⚠️ Schedule already exists for client {client_id} on {scheduled_datetime.date()} at {data.scheduledTime} - returning existing schedule"
                )
                # Update client with scheduled time (in case it wasn't set)
                client.scheduled_start_time = scheduled_start
                client.scheduled_end_time = scheduled_end
                client.scheduling_status = "pending_provider_confirmation"
                db.commit()
                db.refresh(existing_schedule)

                # Use existing schedule for the rest of the function
                new_schedule = existing_schedule
                send_notification = False  # Don't send duplicate notification
            else:
                # Update client with scheduled time
                client.scheduled_start_time = scheduled_start
                client.scheduled_end_time = scheduled_end
                client.scheduling_status = "pending_provider_confirmation"

                # Extract address from form_data if available
                address = None
                if client.form_data and isinstance(client.form_data, dict):
                    address = client.form_data.get("address") or client.form_data.get(
                        "serviceAddress"
                    )

                # Create a Schedule record with pending approval status
                # This ensures the provider sees it in their schedule view and gets a notification badge
                new_schedule = Schedule(
                    user_id=client.user_id,
                    client_id=client.id,
                    title=f"Cleaning for {client.contact_name or client.business_name}",
                    description="Client-requested cleaning appointment",
                    service_type=client.property_type or "standard",
                    scheduled_date=scheduled_datetime,
                    start_time=data.scheduledTime,
                    end_time=data.endTime,
                    duration_minutes=data.durationMinutes,
                    status="scheduled",
                    approval_status="pending",  # This triggers the notification badge
                    address=address,
                    price=None,  # Will be set when provider confirms
                    is_recurring=False,
                    calendly_booking_method="client_selected",
                )

                db.add(new_schedule)
                db.commit()
                db.refresh(client)
                db.refresh(new_schedule)

                logger.info(
                    f"✅ Client {client_id} submitted schedule: {scheduled_start} - {scheduled_end}"
                )
                logger.info(
                    f"✅ Created new Schedule record {new_schedule.id} with approval_status='pending'"
                )
                send_notification = True  # Send notification for new schedule

        except Exception as parse_err:
            logger.error(f"❌ Failed to parse schedule times or create schedule: {parse_err}")
            db.rollback()
            raise HTTPException(status_code=400, detail="Invalid date/time format") from parse_err

        # Send notification email to provider (only for new schedules)
        try:
            if provider.email and send_notification:
                # Parse times for email display
                start_dt = datetime.fromisoformat(scheduled_start)
                end_dt = datetime.fromisoformat(scheduled_end)

                provider_content = f"""
                <p>Hi {provider.full_name or business_name},</p>
                <p><strong>{client.contact_name or client.business_name}</strong> has selected their preferred cleaning time!</p>

                <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 16px; padding: 24px; margin: 24px 0; border-left: 4px solid #0ea5e9;">
                  <p style="color: #0c4a6e; font-weight: 600; margin-bottom: 16px; font-size: 16px;">📅 Requested Cleaning Schedule</p>
                  <div style="background: white; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                    <p style="color: #0c4a6e; font-size: 15px; margin: 8px 0;">
                      <strong>Date:</strong> {start_dt.strftime("%A, %B %d, %Y")}
                    </p>
                    <p style="color: #0c4a6e; font-size: 15px; margin: 8px 0;">
                      <strong>Time:</strong> {start_dt.strftime("%I:%M %p")} - {end_dt.strftime("%I:%M %p")}
                    </p>
                    <p style="color: #64748b; font-size: 13px; margin: 8px 0;">
                      Duration: {data.durationMinutes} minutes
                    </p>
                  </div>
                </div>

                <div style="background: #fef3c7; border-radius: 12px; padding: 16px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                  <p style="color: #92400e; font-size: 14px; margin: 0;">
                    ⏰ <strong>Action Required:</strong> Please review and confirm this schedule in your dashboard, or propose an alternative time if needed.
                  </p>
                </div>

                <p style="margin-top: 24px;">
                  <a href="{config.custom_forms_domain or 'https://cleanenroll.com'}/schedule"
                     style="display: inline-block; background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px;">
                    Review Schedule →
                  </a>
                </p>

                <p style="color: #64748b; font-size: 13px; margin-top: 20px;">
                  Client: {client.contact_name or client.business_name}<br>
                  {f"Email: {client.email}" if client.email else ""}<br>
                  {f"Phone: {client.phone}" if client.phone else ""}
                </p>
                """

                await send_email(
                    to=provider.email,
                    subject=f"New Schedule Request from {client.contact_name or client.business_name}",
                    title="Client Selected Cleaning Time! 📅",
                    content_html=provider_content,
                    is_user_email=True,
                )

                logger.info(f"✅ Schedule notification sent to provider {provider.email}")

        except Exception as email_err:
            logger.warning(f"⚠️ Failed to send schedule notification email: {email_err}")
            # Don't fail the request if email fails

        return {
            "success": True,
            "message": "Schedule submitted successfully. Provider will be notified.",
            "scheduledStartTime": scheduled_start,
            "scheduledEndTime": scheduled_end,
            "scheduleId": new_schedule.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting client schedule: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# QUOTE APPROVAL ENDPOINTS
# ============================================================================


class QuoteApprovalRequest(BaseModel):
    """Schema for provider approving a quote as-is"""
    notes: Optional[str] = None


class QuoteAdjustmentRequest(BaseModel):
    """Schema for provider adjusting a quote"""
    adjusted_amount: float
    adjustment_notes: str

    @field_validator("adjusted_amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Adjusted amount must be greater than 0")
        if v > 1000000:
            raise ValueError("Adjusted amount must be less than $1,000,000")
        return v


@router.get("/pending-review")
async def get_pending_review_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all clients with pending quote reviews for the current provider.
    Returns clients with quote_status='pending_review' ordered by submission date.
    """
    clients = (
        db.query(Client)
        .filter(
            Client.user_id == current_user.id,
            Client.quote_status == "pending_review"
        )
        .order_by(Client.quote_submitted_at.desc())
        .all()
    )

    return {
        "clients": [
            {
                "id": client.id,
                "public_id": client.public_id,
                "business_name": client.business_name,
                "contact_name": client.contact_name,
                "email": client.email,
                "phone": client.phone,
                "property_type": client.property_type,
                "property_size": client.property_size,
                "frequency": client.frequency,
                "original_quote_amount": client.original_quote_amount,
                "quote_submitted_at": client.quote_submitted_at.isoformat() if client.quote_submitted_at else None,
                "form_data": client.form_data,
            }
            for client in clients
        ],
        "count": len(clients),
    }


@router.get("/{client_id}/quote-review")
async def get_quote_review_details(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed quote information for provider review.
    Includes client details, form data, and quote history.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get quote history
    from ..models import QuoteHistory
    history = (
        db.query(QuoteHistory)
        .filter(QuoteHistory.client_id == client_id)
        .order_by(QuoteHistory.created_at.desc())
        .all()
    )

    return {
        "client": {
            "id": client.id,
            "public_id": client.public_id,
            "business_name": client.business_name,
            "contact_name": client.contact_name,
            "email": client.email,
            "phone": client.phone,
            "property_type": client.property_type,
            "property_size": client.property_size,
            "frequency": client.frequency,
            "status": client.status,
            "quote_status": client.quote_status,
            "original_quote_amount": client.original_quote_amount,
            "adjusted_quote_amount": client.adjusted_quote_amount,
            "quote_adjustment_notes": client.quote_adjustment_notes,
            "quote_submitted_at": client.quote_submitted_at.isoformat() if client.quote_submitted_at else None,
            "quote_approved_at": client.quote_approved_at.isoformat() if client.quote_approved_at else None,
            "form_data": client.form_data,
            "notes": client.notes,
            "created_at": client.created_at.isoformat(),
        },
        "history": [
            {
                "id": h.id,
                "action": h.action,
                "amount": h.amount,
                "notes": h.notes,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
    }


@router.post("/{client_id}/approve-quote")
async def approve_quote(
    client_id: int,
    data: QuoteApprovalRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider approves the automated quote as-is.
    Updates quote status, sends approval email to client, and prepares for scheduling.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.quote_status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Quote is not pending review (current status: {client.quote_status})"
        )

    # Update client quote status
    client.quote_status = "approved"
    client.quote_approved_at = func.now()
    client.quote_approved_by = current_user.email or str(current_user.id)

    # Create quote history entry
    from ..models import QuoteHistory
    history_entry = QuoteHistory(
        client_id=client.id,
        action="approved",
        amount=client.original_quote_amount,
        notes=data.notes or "Provider approved quote as-is",
        created_by=f"provider:{current_user.email or current_user.id}",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(client)

    logger.info(
        f"✅ Quote approved for client {client.id} by provider {current_user.id}"
    )

    # Send approval email to client
    if client.email:
        from ..email_service import send_quote_approved_email
        
        # Get business name from business_config
        business_name = (
            current_user.business_config.business_name 
            if current_user.business_config and current_user.business_config.business_name 
            else "Service Provider"
        )
        
        background_tasks.add_task(
            send_quote_approved_email,
            to=client.email,
            client_name=client.contact_name or client.business_name,
            business_name=business_name,
            final_quote_amount=client.original_quote_amount or 0,
            was_adjusted=False,
            adjustment_notes=None,
            client_public_id=client.public_id,
        )

    return {
        "message": "Quote approved successfully",
        "client_id": client.id,
        "client_public_id": client.public_id,
        "quote_status": client.quote_status,
        "approved_amount": client.original_quote_amount,
    }


@router.post("/{client_id}/adjust-quote")
async def adjust_quote(
    client_id: int,
    data: QuoteAdjustmentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider adjusts the automated quote with a new amount and explanation.
    Updates quote status, stores adjustment, sends email to client.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.quote_status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Quote is not pending review (current status: {client.quote_status})"
        )

    # Validate adjustment notes
    if not data.adjustment_notes or len(data.adjustment_notes.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Adjustment notes must be at least 10 characters"
        )

    # Update client with adjusted quote
    client.quote_status = "adjusted"
    client.adjusted_quote_amount = data.adjusted_amount
    client.quote_adjustment_notes = data.adjustment_notes
    client.quote_approved_at = func.now()
    client.quote_approved_by = current_user.email or str(current_user.id)

    # Create quote history entry
    from ..models import QuoteHistory
    history_entry = QuoteHistory(
        client_id=client.id,
        action="adjusted",
        amount=data.adjusted_amount,
        notes=data.adjustment_notes,
        created_by=f"provider:{current_user.email or current_user.id}",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(client)

    logger.info(
        f"✅ Quote adjusted for client {client.id} by provider {current_user.id}: "
        f"${client.original_quote_amount} → ${data.adjusted_amount}"
    )

    # Send adjustment email to client
    if client.email:
        from ..email_service import send_quote_approved_email
        
        # Get business name from business_config
        business_name = (
            current_user.business_config.business_name 
            if current_user.business_config and current_user.business_config.business_name 
            else "Service Provider"
        )
        
        background_tasks.add_task(
            send_quote_approved_email,
            to=client.email,
            client_name=client.contact_name or client.business_name,
            business_name=business_name,
            final_quote_amount=data.adjusted_amount,
            was_adjusted=True,
            adjustment_notes=data.adjustment_notes,
            client_public_id=client.public_id,
        )

    return {
        "message": "Quote adjusted successfully",
        "client_id": client.id,
        "client_public_id": client.public_id,
        "quote_status": client.quote_status,
        "original_amount": client.original_quote_amount,
        "adjusted_amount": data.adjusted_amount,
        "adjustment_notes": data.adjustment_notes,
    }


@router.post("/{client_id}/reject-quote")
async def reject_quote(
    client_id: int,
    data: QuoteApprovalRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider rejects the quote request.
    Updates status and optionally notifies client.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.quote_status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Quote is not pending review (current status: {client.quote_status})"
        )

    # Update client quote status
    client.quote_status = "rejected"
    client.quote_approved_at = func.now()
    client.quote_approved_by = current_user.email or str(current_user.id)
    if data.notes:
        client.quote_adjustment_notes = data.notes

    # Create quote history entry
    from ..models import QuoteHistory
    history_entry = QuoteHistory(
        client_id=client.id,
        action="rejected",
        amount=client.original_quote_amount,
        notes=data.notes or "Provider rejected quote request",
        created_by=f"provider:{current_user.email or current_user.id}",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(client)

    logger.info(
        f"❌ Quote rejected for client {client.id} by provider {current_user.id}"
    )

    return {
        "message": "Quote rejected",
        "client_id": client.id,
        "quote_status": client.quote_status,
    }


# ============================================
# Quote Requests Dashboard Endpoints
# ============================================
