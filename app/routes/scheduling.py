import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Client, Contract, SchedulingProposal, Schedule
from ..auth import get_current_user
from ..email_service import (
    send_scheduling_proposal_email,
    send_scheduling_accepted_email,
    send_scheduling_counter_proposal_email
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


@router.get("/info/{client_id}")
async def get_scheduling_info_by_client(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for client to get scheduling info.
    Returns business info, working hours, and estimated duration.
    """
    from ..models import BusinessConfig
    from .upload import generate_presigned_url
    
    # Get client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get provider/business info
    user = db.query(User).filter(User.id == client.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == client.user_id
    ).first()
    
    # Calculate estimated duration from contract quote or client's form_data
    estimated_duration = 120  # Default 2 hours in minutes
    
    if client.form_data:
        form_data = client.form_data
        
        # Try to get estimated hours from contract if available
        # First check if there's a contract for this client
        from ..models import Contract
        contract = db.query(Contract).filter(
            Contract.client_id == client_id,
            Contract.status.in_(["new", "sent", "signed"])
        ).order_by(Contract.created_at.desc()).first()
        
        if contract and business_config:
            # Recalculate quote to get estimated hours
            from .contracts_pdf import calculate_quote
            try:
                quote = calculate_quote(business_config, form_data)
                if quote.get('estimated_hours'):
                    estimated_duration = int(quote['estimated_hours'] * 60)  # Convert hours to minutes
                    logger.info(f"📊 Using contract estimated duration: {estimated_duration} minutes ({quote['estimated_hours']} hours)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to calculate quote for duration: {e}")
        
        # Fallback to property size calculation if quote calculation failed
        if estimated_duration == 120:  # Still default
            property_size = form_data.get('propertySize') or form_data.get('property_size')
            if property_size and business_config and business_config.cleaning_time_per_sqft:
                estimated_duration = max(60, int(property_size) * business_config.cleaning_time_per_sqft // 100)
                logger.info(f"📊 Using property size estimated duration: {estimated_duration} minutes")
    
    # Get working hours from business config
    working_hours = {"start": "09:00", "end": "17:00"}
    working_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    buffer_time = 30  # Default 30 minutes between appointments
    
    if business_config:
        if business_config.working_hours:
            working_hours = business_config.working_hours
        if business_config.working_days:
            working_days = business_config.working_days
        if business_config.buffer_time:
            buffer_time = business_config.buffer_time
    
    # Get business branding
    business_name = "Service Provider"
    logo_url = None
    
    if business_config:
        business_name = business_config.business_name or user.full_name or "Service Provider"
        # Generate presigned URL for logo if it exists
        if business_config.logo_url:
            try:
                logo_url = generate_presigned_url(business_config.logo_url)
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate presigned URL for logo: {e}")
    elif user:
        business_name = user.full_name or "Service Provider"
    
    # Check if provider has Calendly integration
    from ..models import CalendlyIntegration
    has_calendly = db.query(CalendlyIntegration).filter(
        CalendlyIntegration.user_id == client.user_id
    ).first() is not None
    
    # Check if meetings are required
    meetings_required = business_config.meetings_required if business_config else False
    
    return {
        "business_name": business_name,
        "logo_url": logo_url,
        "estimated_duration": estimated_duration,
        "working_hours": working_hours,
        "working_days": working_days,
        "buffer_time": buffer_time,
        "meetings_required": meetings_required,
        "has_calendly": has_calendly
    }


class ClientBookingRequest(BaseModel):
    client_id: int
    start_time: str  # ISO format
    end_time: str  # ISO format


@router.post("/book")
async def create_client_booking(
    data: ClientBookingRequest,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for client to book an appointment.
    Creates a PENDING schedule entry that requires provider approval.
    Works even if contract is not yet created (handles race condition).
    """
    from ..models import BusinessConfig
    from ..email_service import send_pending_booking_notification
    
    logger.info(f"📅 Client booking request for client {data.client_id}")
    
    # Get client
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get the most recent contract for this client
    contract = db.query(Contract).filter(
        Contract.client_id == data.client_id
    ).order_by(Contract.created_at.desc()).first()
    
    # If no contract exists, we'll create a schedule entry anyway
    # The contract might be generated by a background job
    if not contract:
        logger.info(f"⚠️ No contract found for client {data.client_id}, creating schedule without contract reference")
    
    # Get provider
    user = db.query(User).filter(User.id == client.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Parse times - treat as local time (no timezone conversion)
    # Remove any timezone info to treat as naive local time
    start_time_str = data.start_time.replace('Z', '').split('+')[0].split('.')[0]
    end_time_str = data.end_time.replace('Z', '').split('+')[0].split('.')[0]
    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.fromisoformat(end_time_str)
    duration_minutes = int((end_time - start_time).total_seconds() / 60)
    
    # Format times for display (24h format for storage)
    start_time_24h = start_time.strftime("%H:%M")
    end_time_24h = end_time.strftime("%H:%M")
    start_time_display = start_time.strftime("%I:%M %p")
    end_time_display = end_time.strftime("%I:%M %p")
    
    # Create schedule entry with PENDING approval status
    # Use contract info if available, otherwise use client info
    title = f"Service Appointment - {client.contact_name or client.business_name}"
    description = f"Service appointment for {client.business_name}"
    price = None
    
    if contract:
        title = f"{contract.title} - {client.contact_name or client.business_name}"
        description = contract.description or description
        price = contract.total_value
    
    schedule = Schedule(
        user_id=client.user_id,
        client_id=client.id,
        title=title,
        description=description,
        service_type=contract.contract_type if contract else "standard",
        scheduled_date=start_time.date(),
        start_time=start_time_24h,
        end_time=end_time_24h,
        duration_minutes=duration_minutes,
        status="scheduled",
        approval_status="pending",  # Requires provider approval
        address=client.form_data.get('address') if client.form_data else None,
        price=price,
        notes="Booked by client - awaiting provider approval" + ("" if contract else " (contract pending)")
    )
    db.add(schedule)
    
    # Update client status to pending_approval
    client.status = "pending_approval"
    
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"✅ Client booking created (pending): schedule {schedule.id}")
    
    # Send notification email to provider about pending booking
    try:
        if user.email:
            await send_pending_booking_notification(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.contact_name or client.business_name,
                scheduled_date=start_time.strftime("%Y-%m-%d"),
                start_time=start_time_display,
                end_time=end_time_display,
                property_address=client.form_data.get('address') if client.form_data else None,
                schedule_id=schedule.id
            )
            logger.info(f"📧 Pending booking notification sent to provider {user.email}")
    except Exception as e:
        logger.error(f"Failed to send pending booking notification: {e}")
    
    return {
        "message": "Booking request submitted - awaiting provider approval",
        "schedule_id": schedule.id,
        "scheduled_date": start_time.strftime("%Y-%m-%d"),
        "start_time": start_time_display,
        "end_time": end_time_display,
        "duration_minutes": duration_minutes,
        "status": "pending"
    }


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
    
    # Note: Contract status stays as 'signed' - 'scheduled' is a client status, not contract status
    
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
    
    return {
        "message": "Time slot accepted", 
        "proposal_id": proposal_id,
        "schedule_id": schedule.id,
        "client_status": client.status
    }


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



@router.get("/public/contract/{contract_public_id}")
async def get_public_scheduling_info(
    contract_public_id: str,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for client to get scheduling info for a contract.
    Returns contract details, business info, and available time slots.
    """
    from ..models import BusinessConfig
    from .upload import generate_presigned_url
    
    # Find contract by public_id
    contract = db.query(Contract).filter(
        Contract.public_id == contract_public_id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get client info
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get provider/business info
    user = db.query(User).filter(User.id == contract.user_id).first()
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == contract.user_id
    ).first()
    
    # Calculate estimated duration from contract quote or client's form_data
    estimated_duration = 120  # Default 2 hours in minutes
    
    # Try to get from client's form_data and recalculate quote
    if client.form_data and business_config:
        form_data = client.form_data
        
        # Recalculate quote to get estimated hours
        from .contracts_pdf import calculate_quote
        try:
            quote = calculate_quote(business_config, form_data)
            if quote.get('estimated_hours'):
                estimated_duration = int(quote['estimated_hours'] * 60)  # Convert hours to minutes
                logger.info(f"📊 Using contract estimated duration: {estimated_duration} minutes ({quote['estimated_hours']} hours)")
        except Exception as e:
            logger.warning(f"⚠️ Failed to calculate quote for duration: {e}")
            
            # Fallback to property size calculation
            property_size = form_data.get('propertySize') or form_data.get('property_size')
            if property_size and business_config.cleaning_time_per_sqft:
                estimated_duration = max(60, int(property_size) * business_config.cleaning_time_per_sqft // 100)
                logger.info(f"📊 Using property size estimated duration: {estimated_duration} minutes")
    
    # Get working hours from business config
    working_hours = {
        "start": "09:00",
        "end": "17:00"
    }
    working_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    day_schedules = None
    off_work_periods = None
    buffer_time = 30  # Default 30 minutes between appointments
    
    if business_config:
        if business_config.working_hours:
            working_hours = business_config.working_hours
        if business_config.working_days:
            working_days = business_config.working_days
        if business_config.day_schedules:
            day_schedules = business_config.day_schedules
        if business_config.off_work_periods:
            off_work_periods = business_config.off_work_periods
        if business_config.buffer_time:
            buffer_time = business_config.buffer_time
    
    # Get business branding
    business_name = "Service Provider"
    logo_url = None
    
    if business_config:
        business_name = business_config.business_name or user.full_name or "Service Provider"
        # Generate presigned URL for logo if it exists
        if business_config.logo_url:
            try:
                logo_url = generate_presigned_url(business_config.logo_url)
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate presigned URL for logo: {e}")
    elif user:
        business_name = user.full_name or "Service Provider"
    
    return {
        "contract_id": contract.id,
        "contract_public_id": contract.public_id,
        "contract_title": contract.title,
        "client_name": client.contact_name or client.business_name,
        "business_name": business_name,
        "logo_url": logo_url,
        "estimated_duration": estimated_duration,
        "working_hours": working_hours,
        "working_days": working_days,
        "day_schedules": day_schedules,
        "off_work_periods": off_work_periods,
        "buffer_time": buffer_time,
        "status": contract.status
    }


class DirectBookingRequest(BaseModel):
    contract_public_id: str
    selected_date: str  # YYYY-MM-DD
    selected_time: str  # HH:MM


@router.post("/public/book")
async def create_direct_booking(
    data: DirectBookingRequest,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for client to directly book a time slot.
    Creates a schedule entry without requiring provider proposals.
    """
    logger.info(f"📅 Direct booking request for contract {data.contract_public_id}")
    
    # Find contract by public_id
    contract = db.query(Contract).filter(
        Contract.public_id == data.contract_public_id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check contract status - must be signed
    if contract.status not in ["signed", "new"]:
        raise HTTPException(status_code=400, detail=f"Contract status is '{contract.status}', booking not allowed")
    
    # Get client and user
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    user = db.query(User).filter(User.id == contract.user_id).first()
    
    if not client or not user:
        raise HTTPException(status_code=404, detail="Client or provider not found")
    
    # Get business config for duration calculation
    from ..models import BusinessConfig
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == contract.user_id
    ).first()
    
    # Calculate duration from contract quote or client's form_data
    estimated_duration = 120  # Default 2 hours in minutes
    
    if client.form_data and business_config:
        form_data = client.form_data
        
        # Try to get estimated hours from contract quote
        from .contracts_pdf import calculate_quote
        try:
            quote = calculate_quote(business_config, form_data)
            if quote.get('estimated_hours'):
                estimated_duration = int(quote['estimated_hours'] * 60)  # Convert hours to minutes
                logger.info(f"📊 Using contract estimated duration: {estimated_duration} minutes ({quote['estimated_hours']} hours)")
        except Exception as e:
            logger.warning(f"⚠️ Failed to calculate quote for duration: {e}")
            
            # Fallback to property size calculation
            property_size = form_data.get('propertySize') or form_data.get('property_size')
            if property_size and business_config.cleaning_time_per_sqft:
                estimated_duration = max(60, int(property_size) * business_config.cleaning_time_per_sqft // 100)
                logger.info(f"📊 Using property size estimated duration: {estimated_duration} minutes")
    
    # Calculate end time
    start_hour, start_min = map(int, data.selected_time.split(':'))
    end_hour = start_hour + (estimated_duration // 60)
    end_min = start_min + (estimated_duration % 60)
    if end_min >= 60:
        end_hour += 1
        end_min -= 60
    end_time = f"{end_hour:02d}:{end_min:02d}"
    
    # Format times for display
    def format_time_12h(time_str):
        hour, minute = map(int, time_str.split(':'))
        period = "AM" if hour < 12 else "PM"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        return f"{display_hour}:{minute:02d} {period}"
    
    start_time_display = format_time_12h(data.selected_time)
    end_time_display = format_time_12h(end_time)
    
    # Create schedule entry
    schedule = Schedule(
        user_id=contract.user_id,
        client_id=client.id,
        title=f"{contract.title} - {client.contact_name or client.business_name}",
        description=contract.description or f"Service appointment for {client.business_name}",
        service_type=contract.contract_type or "standard",
        scheduled_date=datetime.fromisoformat(data.selected_date),
        start_time=start_time_display,
        end_time=end_time_display,
        duration_minutes=estimated_duration,
        status="scheduled",
        approval_status="accepted",
        address=client.form_data.get('address') if client.form_data else None,
        price=contract.total_value,
        notes="Booked directly by client"
    )
    db.add(schedule)
    
    # Note: Contract status stays as 'signed' - 'scheduled' is a client status, not contract status
    
    # Update client status to scheduled
    client.status = "scheduled"
    
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"✅ Direct booking created: schedule {schedule.id} for {data.selected_date} at {data.selected_time}")
    
    # Send confirmation email to provider
    try:
        if user.email:
            await send_scheduling_accepted_email(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.contact_name or client.business_name,
                contract_id=contract.id,
                selected_date=data.selected_date,
                start_time=start_time_display,
                end_time=end_time_display,
                property_address=client.form_data.get('address') if client.form_data else None
            )
            logger.info(f"📧 Booking confirmation email sent to provider {user.email}")
    except Exception as e:
        logger.error(f"Failed to send booking confirmation email: {e}")
    
    return {
        "message": "Booking confirmed",
        "schedule_id": schedule.id,
        "scheduled_date": data.selected_date,
        "start_time": start_time_display,
        "end_time": end_time_display,
        "duration_minutes": estimated_duration
    }
