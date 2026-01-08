import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Client, Contract, SchedulingProposal, Schedule
from ..models_invoice import Invoice
from ..auth import get_current_user
from ..email_service import (
    send_scheduling_proposal_email,
    send_scheduling_accepted_email,
    send_scheduling_counter_proposal_email
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


class TimeSlot(BaseModel):
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    recommended: bool = False


class ProposalCreate(BaseModel):
    contract_id: int
    time_slots: List[TimeSlot]
    proposed_by: str = "provider"


class ProposalResponse(BaseModel):
    id: int
    contract_id: int
    client_id: int
    status: str
    proposal_round: int
    proposed_by: str
    time_slots: List[dict]
    selected_slot_date: Optional[str]
    selected_slot_start_time: Optional[str]
    selected_slot_end_time: Optional[str]
    expires_at: Optional[str]
    created_at: str


class ClientAcceptSlot(BaseModel):
    slot_date: str
    slot_start_time: str
    slot_end_time: str


class ClientCounterProposal(BaseModel):
    preferred_days: str  # "M,T,W,Th,F"
    preferred_time_window: str  # "18:00-20:00"
    client_notes: Optional[str] = None


@router.post("/proposals")
async def create_scheduling_proposal(
    data: ProposalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Provider creates initial scheduling proposal with 3 time slots"""
    logger.info(f"📅 Creating scheduling proposal for contract {data.contract_id}")
    
    # Verify contract exists and belongs to user
    contract = db.query(Contract).filter(
        Contract.id == data.contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check if proposal already exists - if so, update it instead of creating new
    existing = db.query(SchedulingProposal).filter(
        SchedulingProposal.contract_id == data.contract_id,
        SchedulingProposal.status == "pending"
    ).first()
    
    if existing:
        logger.info(f"⚠️ Pending proposal already exists for contract {data.contract_id}, updating it")
        # Update existing proposal
        existing.time_slots = [slot.dict() for slot in data.time_slots]
        existing.expires_at = datetime.utcnow() + timedelta(hours=48)
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        proposal = existing
    else:
        # Create new proposal
        proposal = SchedulingProposal(
            contract_id=data.contract_id,
            client_id=contract.client_id,
            user_id=current_user.id,
            proposed_by=data.proposed_by,
            time_slots=[slot.dict() for slot in data.time_slots],
            status="pending",
            proposal_round=1,
            expires_at=datetime.utcnow() + timedelta(hours=48)
        )
        
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        
    # Send email to client
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if client and client.email:
        try:
            await send_scheduling_proposal_email(
                client_email=client.email,
                client_name=client.contact_name or client.business_name,
                provider_name=current_user.full_name or "Your Service Provider",
                contract_id=contract.id,
                time_slots=proposal.time_slots,
                expires_at=proposal.expires_at.isoformat() if proposal.expires_at else ""
            )
            logger.info(f"📧 Scheduling proposal email sent to {client.email}")
        except Exception as e:
            logger.error(f"Failed to send scheduling proposal email: {e}")
    
    return {
        "id": proposal.id,
        "contract_id": proposal.contract_id,
        "status": proposal.status,
        "time_slots": proposal.time_slots,
        "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None
    }


@router.get("/proposals/contract/{contract_id}")
async def get_contract_proposals(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all proposals for a contract"""
    # Verify contract access
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    proposals = db.query(SchedulingProposal).filter(
        SchedulingProposal.contract_id == contract_id
    ).order_by(SchedulingProposal.created_at.desc()).all()
    
    return [{
        "id": p.id,
        "contract_id": p.contract_id,
        "status": p.status,
        "proposal_round": p.proposal_round,
        "proposed_by": p.proposed_by,
        "time_slots": p.time_slots,
        "selected_slot_date": p.selected_slot_date.isoformat() if p.selected_slot_date else None,
        "selected_slot_start_time": p.selected_slot_start_time,
        "selected_slot_end_time": p.selected_slot_end_time,
        "expires_at": p.expires_at.isoformat() if p.expires_at else None,
        "created_at": p.created_at.isoformat()
    } for p in proposals]


@router.post("/proposals/{proposal_id}/accept")
async def client_accept_slot(
    proposal_id: int,
    data: ClientAcceptSlot,
    db: Session = Depends(get_db)
):
    """Client accepts a proposed time slot"""
    from ..models import Schedule, BusinessConfig
    from ..models_invoice import Invoice
    from ..email_service import send_invoice_payment_link_email
    from ..config import DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT, FRONTEND_URL
    
    logger.info(f"📥 Received slot acceptance for proposal {proposal_id}: {data.dict()}")
    
    proposal = db.query(SchedulingProposal).filter(
        SchedulingProposal.id == proposal_id
    ).first()
    
    if not proposal:
        logger.error(f"❌ Proposal {proposal_id} not found")
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status != "pending":
        logger.error(f"❌ Proposal {proposal_id} status is '{proposal.status}', not 'pending'")
        raise HTTPException(status_code=400, detail=f"Proposal status is '{proposal.status}', not pending. It may have already been accepted.")
    
    # Get contract and client
    contract = db.query(Contract).filter(Contract.id == proposal.contract_id).first()
    client = db.query(Client).filter(Client.id == proposal.client_id).first()
    user = db.query(User).filter(User.id == proposal.user_id).first()
    
    if not contract or not client or not user:
        raise HTTPException(status_code=404, detail="Contract, client, or user not found")
    
    # Update proposal
    proposal.status = "accepted"
    proposal.selected_slot_date = datetime.fromisoformat(data.slot_date)
    proposal.selected_slot_start_time = data.slot_start_time
    proposal.selected_slot_end_time = data.slot_end_time
    proposal.responded_at = datetime.utcnow()
    
    # Update client status to 'scheduled'
    client.status = "scheduled"
    logger.info(f"✅ Updated client {client.id} status to 'scheduled'")
    
    # Create calendar event (Schedule)
    schedule = Schedule(
        user_id=proposal.user_id,
        client_id=proposal.client_id,
        title=f"{contract.title} - {client.contact_name or client.business_name}",
        description=contract.description or f"Service appointment for {client.business_name}",
        service_type=contract.contract_type or "standard",
        scheduled_date=datetime.fromisoformat(data.slot_date),
        start_time=data.slot_start_time,
        end_time=data.slot_end_time,
        status="scheduled",
        address=getattr(client, 'address', None),
        price=contract.total_value,
        notes=f"Scheduled from proposal #{proposal_id}"
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"✅ Created calendar event {schedule.id} for client {client.business_name} on {data.slot_date}")
    
    # Send confirmation email to provider
    try:
        if user.email:
            await send_scheduling_accepted_email(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.contact_name or client.business_name,
                contract_id=contract.id,
                selected_date=data.slot_date,
                start_time=data.slot_start_time,
                end_time=data.slot_end_time,
                property_address=getattr(client, 'address', None)
            )
            logger.info(f"📧 Scheduling acceptance email sent to provider")
    except Exception as e:
        logger.error(f"Failed to send scheduling acceptance email: {e}")
    
    # Auto-create invoice and send payment link
    invoice_id = None
    try:
        invoice_id = await _create_invoice_for_schedule(
            schedule=schedule,
            user=user,
            client=client,
            contract=contract,
            db=db
        )
    except Exception as e:
        logger.error(f"⚠️ Failed to create invoice: {e}")
    
    return {
        "message": "Time slot accepted", 
        "proposal_id": proposal_id,
        "schedule_id": schedule.id,
        "client_status": client.status,
        "invoice_id": invoice_id
    }


async def _create_invoice_for_schedule(
    schedule: Schedule,
    user: User,
    client: Client,
    contract: Contract,
    db: Session
) -> Optional[int]:
    """Create invoice and send payment link when schedule is confirmed"""
    from ..models import BusinessConfig
    from ..models_invoice import Invoice
    from ..email_service import send_invoice_payment_link_email
    from ..config import DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT, FRONTEND_URL, DODO_DEFAULT_TAX_CATEGORY
    from dodopayments import AsyncDodoPayments
    
    logger.info(f"📄 Creating invoice for schedule {schedule.id}")
    
    # Get business config
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == user.id
    ).first()
    
    # Determine base amount
    base_amount = schedule.price or (contract.total_value if contract else 0)
    
    if base_amount <= 0:
        logger.warning(f"⚠️ Cannot create invoice with zero amount")
        return None
    
    # Determine service type
    service_type = client.frequency or "one-time"
    is_recurring = service_type in ["weekly", "bi-weekly", "monthly"]
    
    # Calculate frequency discount
    frequency_discount = 0
    if business_config:
        if service_type == "weekly" and business_config.discount_weekly:
            frequency_discount = base_amount * (business_config.discount_weekly / 100)
        elif service_type == "bi-weekly" and business_config.discount_monthly:
            frequency_discount = base_amount * (business_config.discount_monthly / 100 / 2)
        elif service_type == "monthly" and business_config.discount_monthly:
            frequency_discount = base_amount * (business_config.discount_monthly / 100)
    
    total_amount = base_amount - frequency_discount
    
    # Generate invoice number
    year = datetime.now().year
    count = db.query(Invoice).filter(
        Invoice.user_id == user.id,
        Invoice.created_at >= datetime(year, 1, 1)
    ).count() + 1
    invoice_number = f"INV-{year}-{user.id:04d}-{count:04d}"
    
    # Billing interval
    billing_interval = None
    billing_interval_count = 1
    if is_recurring:
        intervals = {"weekly": ("week", 1), "bi-weekly": ("week", 2), "monthly": ("month", 1)}
        billing_interval, billing_interval_count = intervals.get(service_type, ("month", 1))
    
    # Create invoice
    invoice = Invoice(
        user_id=user.id,
        client_id=client.id,
        contract_id=contract.id if contract else None,
        schedule_id=schedule.id,
        invoice_number=invoice_number,
        title=f"Cleaning Service - {schedule.title}",
        description=f"Service scheduled for {schedule.scheduled_date.strftime('%B %d, %Y')}",
        service_type=service_type,
        base_amount=base_amount,
        frequency_discount=frequency_discount,
        addon_amount=0,
        tax_amount=0,
        total_amount=total_amount,
        is_recurring=is_recurring,
        recurrence_pattern=service_type if is_recurring else None,
        billing_interval=billing_interval,
        billing_interval_count=billing_interval_count,
        status="pending",
        due_date=datetime.utcnow() + timedelta(days=business_config.payment_due_days if business_config else 15)
    )
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    logger.info(f"✅ Invoice created: {invoice_number}")
    
    # Generate payment link
    if not DODO_PAYMENTS_API_KEY:
        logger.warning("⚠️ DODO_PAYMENTS_API_KEY not configured")
        return invoice.id
    
    business_name = business_config.business_name if business_config else "Cleaning Service"
    
    dodo_client = AsyncDodoPayments(
        bearer_token=DODO_PAYMENTS_API_KEY,
        environment=DODO_PAYMENTS_ENVIRONMENT or "test_mode",
    )
    
    try:
        product_data = {
            "name": f"{invoice.title} - {invoice.invoice_number}",
            "description": invoice.description or f"Cleaning service from {business_name}",
            "price": {"currency": invoice.currency.upper(), "price": int(invoice.total_amount * 100),\n                "type": "one_time_price"},
            "tax_category": DODO_DEFAULT_TAX_CATEGORY,
        }
        
        if is_recurring and billing_interval:
            product_data["billing"] = {"type": "recurring", "interval": billing_interval, "interval_count": billing_interval_count}
        else:
            product_data["billing"] = {"type": "one_time"}
        
        product = await dodo_client.products.create(**product_data)
        product_id = getattr(product, "product_id", None) or product.get("product_id")
        
        return_url = f"{FRONTEND_URL}/payment/success/{invoice.id}"
        
        session = await dodo_client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer={"email": client.email or "", "name": client.contact_name or client.business_name or ""},
            metadata={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number, "provider_user_id": str(user.id), "client_id": str(client.id)},
            return_url=return_url,
        )
        
        checkout_url = getattr(session, "checkout_url", None) or session.get("checkout_url")
        
        invoice.dodo_product_id = product_id
        invoice.dodo_payment_link = checkout_url
        invoice.status = "sent"
        db.commit()
        
        logger.info(f"✅ Payment link generated: {checkout_url}")
        
        # Send email
        if client.email:
            try:
                await send_invoice_payment_link_email(
                    to=client.email,
                    client_name=client.contact_name or client.business_name,
                    business_name=business_name,
                    invoice_number=invoice.invoice_number,
                    invoice_title=invoice.title,
                    total_amount=invoice.total_amount,
                    currency=invoice.currency,
                    due_date=invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else None,
                    payment_link=checkout_url,
                    is_recurring=is_recurring,
                    recurrence_pattern=service_type if is_recurring else None
                )
                logger.info(f"📧 Payment link email sent to {client.email}")
            except Exception as e:
                logger.error(f"❌ Failed to send payment link email: {e}")
        
        return invoice.id
        
    except Exception as e:
        logger.error(f"❌ Failed to create payment link: {e}")
        return invoice.id


@router.post("/proposals/{proposal_id}/counter")
async def client_counter_proposal(
    proposal_id: int,
    data: ClientCounterProposal,
    db: Session = Depends(get_db)
):
    """Client proposes alternative times"""
    proposal = db.query(SchedulingProposal).filter(
        SchedulingProposal.id == proposal_id
    ).first()
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status != "pending":
        raise HTTPException(status_code=400, detail="Proposal is not pending")
    
    if proposal.proposal_round >= 3:
        raise HTTPException(status_code=400, detail="Maximum negotiation rounds reached")
    
    # Update proposal
    proposal.status = "countered"
    proposal.preferred_days = data.preferred_days
    proposal.preferred_time_window = data.preferred_time_window
    proposal.client_notes = data.client_notes
    proposal.responded_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"⏳ Client countered proposal {proposal_id}")
    
    # Send notification email to provider
    try:
        contract = db.query(Contract).filter(Contract.id == proposal.contract_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()
        user = db.query(User).filter(User.id == proposal.user_id).first()
        
        if contract and client and user and user.email:
            await send_scheduling_counter_proposal_email(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.contact_name or client.business_name,
                contract_id=contract.id,
                preferred_days=data.preferred_days,
                time_window=data.preferred_time_window,
                client_notes=data.client_notes
            )
            logger.info(f"📧 Counter-proposal email sent to provider")
    except Exception as e:
        logger.error(f"Failed to send counter-proposal email: {e}")
    
    return {
        "message": "Counter-proposal submitted",
        "proposal_id": proposal_id,
        "round": proposal.proposal_round
    }


@router.get("/proposals/public/{contract_id}")
async def get_public_contract_proposals(
    contract_id: int,
    db: Session = Depends(get_db)
):
    """Public endpoint for client to view proposals (no auth required)"""
    proposals = db.query(SchedulingProposal).filter(
        SchedulingProposal.contract_id == contract_id,
        SchedulingProposal.status.in_(["pending", "countered"])
    ).order_by(SchedulingProposal.created_at.desc()).all()
    
    if not proposals:
        return []
    
    return [{
        "id": p.id,
        "contract_id": p.contract_id,
        "status": p.status,
        "proposal_round": p.proposal_round,
        "time_slots": p.time_slots,
        "expires_at": p.expires_at.isoformat() if p.expires_at else None,
        "created_at": p.created_at.isoformat()
    } for p in proposals]
