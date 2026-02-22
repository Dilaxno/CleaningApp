import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user_with_plan
from ..database import get_db
from ..models import BusinessConfig, Client, Contract, Schedule, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["Schedules"])


class ScheduleCreate(BaseModel):
    clientId: int
    title: str
    description: Optional[str] = None
    serviceType: Optional[str] = None
    scheduledDate: datetime
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    durationMinutes: Optional[int] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    assignedTo: Optional[str] = None
    price: Optional[float] = None
    isRecurring: Optional[bool] = False
    recurrencePattern: Optional[str] = None


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    serviceType: Optional[str] = None
    scheduledDate: Optional[datetime] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    durationMinutes: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    assignedTo: Optional[str] = None
    price: Optional[float] = None
    isRecurring: Optional[bool] = None
    recurrencePattern: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: int
    clientId: int
    clientName: str
    title: str
    description: Optional[str]
    serviceType: Optional[str]
    propertyType: Optional[str] = None
    scheduledDate: datetime
    startTime: Optional[str]
    endTime: Optional[str]
    durationMinutes: Optional[int]
    status: str
    approvalStatus: Optional[str] = (
        "accepted"  # pending, accepted, change_requested, client_counter
    )
    proposedDate: Optional[datetime] = None
    proposedStartTime: Optional[str] = None
    proposedEndTime: Optional[str] = None
    notes: Optional[str]
    address: Optional[str]
    location: Optional[str] = None
    assignedTo: Optional[str]
    price: Optional[float]
    isRecurring: bool
    recurrencePattern: Optional[str]
    calendlyEventUri: Optional[str] = None
    calendlyEventId: Optional[str] = None
    calendlyBookingMethod: Optional[str] = None
    googleCalendarEventId: Optional[str] = None
    contractStatus: Optional[str] = None  # Contract status for validation
    createdAt: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[ScheduleResponse])
async def get_schedules(
    current_user: User = Depends(get_current_user_with_plan), db: Session = Depends(get_db)
):
    """Get all schedules for the current user"""
    schedules = (
        db.query(Schedule)
        .filter(Schedule.user_id == current_user.id)
        .order_by(Schedule.scheduled_date.asc())
        .all()
    )
    result = []
    for s in schedules:
        client = db.query(Client).filter(Client.id == s.client_id).first()
        # Get property type from client
        property_type = None
        if client:
            property_type = client.property_type
            # Also check form_data for property type
            if not property_type and client.form_data:
                property_type = client.form_data.get("propertyType") or client.form_data.get(
                    "property_type"
                )

        # Get contract status for validation
        contract_status = None
        if client:
            contract = (
                db.query(Contract)
                .filter(Contract.client_id == client.id)
                .order_by(Contract.created_at.desc())
                .first()
            )
            if contract:
                contract_status = contract.status

        result.append(
            ScheduleResponse(
                id=s.id,
                clientId=s.client_id,
                clientName=client.business_name if client else "Unknown",
                title=s.title,
                description=s.description,
                serviceType=s.service_type,
                propertyType=property_type,
                scheduledDate=s.scheduled_date,
                startTime=s.start_time,
                endTime=s.end_time,
                durationMinutes=s.duration_minutes,
                status=s.status,
                approvalStatus=s.approval_status or "accepted",
                proposedDate=s.proposed_date,
                proposedStartTime=s.proposed_start_time,
                proposedEndTime=s.proposed_end_time,
                notes=s.notes,
                address=s.address,
                location=s.location,
                assignedTo=s.assigned_to,
                price=s.price,
                isRecurring=s.is_recurring or False,
                recurrencePattern=s.recurrence_pattern,
                calendlyEventUri=s.calendly_event_uri,
                calendlyEventId=s.calendly_event_id,
                calendlyBookingMethod=s.calendly_booking_method,
                contractStatus=contract_status,
                createdAt=s.created_at,
            )
        )
    return result


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Create a new schedule"""
    logger.info(f"📥 Creating schedule for user_id: {current_user.id}")

    client = (
        db.query(Client)
        .filter(Client.id == data.clientId, Client.user_id == current_user.id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    schedule = Schedule(
        user_id=current_user.id,
        client_id=data.clientId,
        title=data.title,
        description=data.description,
        service_type=data.serviceType,
        scheduled_date=data.scheduledDate,
        start_time=data.startTime,
        end_time=data.endTime,
        duration_minutes=data.durationMinutes,
        notes=data.notes,
        address=data.address,
        assigned_to=data.assignedTo,
        price=data.price,
        is_recurring=data.isRecurring,
        recurrence_pattern=data.recurrencePattern,
        status="scheduled",
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return ScheduleResponse(
        id=schedule.id,
        clientId=schedule.client_id,
        clientName=client.business_name,
        title=schedule.title,
        description=schedule.description,
        serviceType=schedule.service_type,
        scheduledDate=schedule.scheduled_date,
        startTime=schedule.start_time,
        endTime=schedule.end_time,
        durationMinutes=schedule.duration_minutes,
        status=schedule.status,
        notes=schedule.notes,
        address=schedule.address,
        assignedTo=schedule.assigned_to,
        price=schedule.price,
        isRecurring=schedule.is_recurring or False,
        recurrencePattern=schedule.recurrence_pattern,
        createdAt=schedule.created_at,
    )


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Update a schedule"""
    from ..services.google_calendar_service import update_calendar_event

    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id)
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if data.title is not None:
        schedule.title = data.title
    if data.description is not None:
        schedule.description = data.description
    if data.serviceType is not None:
        schedule.service_type = data.serviceType
    if data.scheduledDate is not None:
        schedule.scheduled_date = data.scheduledDate
    if data.startTime is not None:
        schedule.start_time = data.startTime
    if data.endTime is not None:
        schedule.end_time = data.endTime
    if data.durationMinutes is not None:
        schedule.duration_minutes = data.durationMinutes
    if data.status is not None:
        schedule.status = data.status
    if data.notes is not None:
        schedule.notes = data.notes
    if data.address is not None:
        schedule.address = data.address
    if data.assignedTo is not None:
        schedule.assigned_to = data.assignedTo
    if data.price is not None:
        schedule.price = data.price
    if data.isRecurring is not None:
        schedule.is_recurring = data.isRecurring
    if data.recurrencePattern is not None:
        schedule.recurrence_pattern = data.recurrencePattern

    db.commit()
    db.refresh(schedule)

    # 🆕 UPDATE GOOGLE CALENDAR EVENT IF EXISTS
    if schedule.google_calendar_event_id:
        try:
            await update_calendar_event(
                user=current_user,
                schedule=schedule,
                google_event_id=schedule.google_calendar_event_id,
                db=db,
            )
            logger.info(f"✅ Google Calendar event updated: {schedule.google_calendar_event_id}")
        except Exception as e:
            logger.error(f"⚠️ Failed to update Google Calendar event: {str(e)}")

    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    return ScheduleResponse(
        id=schedule.id,
        clientId=schedule.client_id,
        clientName=client.business_name if client else "Unknown",
        title=schedule.title,
        description=schedule.description,
        serviceType=schedule.service_type,
        scheduledDate=schedule.scheduled_date,
        startTime=schedule.start_time,
        endTime=schedule.end_time,
        durationMinutes=schedule.duration_minutes,
        status=schedule.status,
        notes=schedule.notes,
        address=schedule.address,
        assignedTo=schedule.assigned_to,
        price=schedule.price,
        isRecurring=schedule.is_recurring or False,
        recurrencePattern=schedule.recurrence_pattern,
        createdAt=schedule.created_at,
    )


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Delete a schedule"""
    from ..services.google_calendar_service import delete_calendar_event

    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id)
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # 🆕 DELETE GOOGLE CALENDAR EVENT IF EXISTS
    if schedule.google_calendar_event_id:
        try:
            await delete_calendar_event(
                user=current_user, google_event_id=schedule.google_calendar_event_id, db=db
            )
            logger.info(f"✅ Google Calendar event deleted: {schedule.google_calendar_event_id}")
        except Exception as e:
            logger.error(f"⚠️ Failed to delete Google Calendar event: {str(e)}")

    db.delete(schedule)
    db.commit()
    return {"message": "Schedule deleted"}


class ScheduleApprovalRequest(BaseModel):
    action: str  # 'accept' or 'request_change'
    proposedDate: Optional[datetime] = None
    proposedStartTime: Optional[str] = None
    proposedEndTime: Optional[str] = None


@router.post("/{schedule_id}/approve")
async def approve_schedule(
    schedule_id: int,
    request: ScheduleApprovalRequest,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Accept or request change for a pending schedule"""
    from .. import email_service
    from ..services.google_calendar_service import create_calendar_event
    from ..services.square_service import create_square_invoice_for_contract

    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if request.action == "accept":
        # Require a fully signed contract before a provider can accept/verify scheduling.
        # This prevents clients from being marked as scheduled/verified before provider signature.
        contract = (
            db.query(Contract)
            .filter(Contract.client_id == schedule.client_id)
            .order_by(Contract.created_at.desc())
            .first()
        )
        if not contract or contract.status != "signed":
            raise HTTPException(
                status_code=400,
                detail="You must review and sign the contract before accepting this appointment. Please go to the Contracts page to sign the contract first.",
            )

        # If this is a client counter-proposal, use the client's proposed time
        if schedule.approval_status == "client_counter" and schedule.proposed_date:
            schedule.scheduled_date = schedule.proposed_date
            schedule.start_time = schedule.proposed_start_time
            schedule.end_time = schedule.proposed_end_time
            # Clear the proposal fields
            schedule.proposed_date = None
            schedule.proposed_start_time = None
            schedule.proposed_end_time = None

        # Accept the appointment
        schedule.approval_status = "accepted"

        # Only the provider accepting the schedule should mark the client as scheduled.
        # The contract must already be fully signed (checked above).
        client = db.query(Client).filter(Client.id == schedule.client_id).first()
        if client:
            client.status = "scheduled"

        # Mark onboarding complete ONLY after provider acceptance.
        contract.client_onboarding_status = "completed"

        # Set contract start date to the scheduled date
        if schedule.scheduled_date and not contract.start_date:
            contract.start_date = schedule.scheduled_date
            logger.info(
                f"📅 Setting contract {contract.id} start_date to {schedule.scheduled_date}"
            )

        # NOTE: Client count is NOT incremented here anymore
        # Client count is incremented when client signs the contract (in clients.py)
        # This ensures the count reflects when the client commits to the service

        db.commit()

        # 🆕 CREATE GOOGLE CALENDAR EVENT AFTER SCHEDULE APPROVAL
        try:
            google_event_id = await create_calendar_event(
                user=current_user, schedule=schedule, db=db
            )
            if google_event_id:
                schedule.google_calendar_event_id = google_event_id
                db.commit()
                logger.info(f"✅ Google Calendar event created: {google_event_id}")
        except Exception as e:
            logger.error(f"⚠️ Failed to create Google Calendar event: {str(e)}")

        # 🆕 CREATE SQUARE INVOICE AFTER SCHEDULE APPROVAL
        # This is the trigger point - provider has accepted the schedule
        try:
            square_result = await create_square_invoice_for_contract(
                contract=contract, client=client, schedule=schedule, user=current_user, db=db
            )

            if square_result.get("success"):
                logger.info(f"✅ Square invoice created: {square_result.get('invoice_id')}")
                # Mark invoice as auto-generated
                contract.invoice_auto_generated = True
                db.commit()

                # Send invoice email from Cleanenroll (not Square)
                # Square is configured with SHARE_MANUALLY so it won't send emails
                if client and client.email and contract.square_invoice_url:
                    try:
                        from ..email_service import send_invoice_payment_link_email

                        # Determine if recurring
                        is_recurring = contract.frequency and contract.frequency not in [
                            "one-time",
                            "One-time",
                        ]

                        logger.info(f"📧 Sending Square deposit invoice email to {client.email}")

                        await send_invoice_payment_link_email(
                            to=client.email,
                            client_name=client.business_name or client.contact_name or "Client",
                            business_name=current_user.full_name
                            or current_user.business_name
                            or "Your Service Provider",
                            invoice_number=f"INV-{contract.public_id[:8].upper()}-DEP",
                            invoice_title=contract.title or "Cleaning Service",
                            total_amount=contract.deposit_amount or (contract.total_value / 2),
                            currency=contract.currency or "USD",
                            due_date=(datetime.utcnow() + timedelta(days=15)).strftime("%B %d, %Y"),
                            payment_link=contract.square_invoice_url,
                            is_recurring=is_recurring,
                            is_deposit=True,
                            deposit_percentage=50,
                            remaining_balance=contract.remaining_balance
                            or (contract.total_value / 2),
                        )
                        logger.info(
                            f"✅ Square deposit invoice email sent successfully to {client.email}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to send Square invoice email to {client.email}: {str(e)}"
                        )
                        logger.exception(e)
                        # Don't fail the schedule approval, but log the error prominently
                        logger.error(
                            f"⚠️ IMPORTANT: Client {client.email} did not receive invoice email. Use /contracts/{contract.id}/send-square-invoice-email to resend."
                        )
                else:
                    if not client:
                        logger.warning(f"⚠️ No client found for contract {contract.id}")
                    elif not client.email:
                        logger.warning(f"⚠️ Client {client.id} has no email address")
                    elif not contract.square_invoice_url:
                        logger.warning(f"⚠️ Contract {contract.id} has no Square invoice URL")
            else:
                # Log but don't fail the schedule approval
                reason = square_result.get("reason", "unknown")
                logger.info(f"ℹ️ Square invoice not created: {reason}")
        except Exception as e:
            # Log error but don't fail the schedule approval
            logger.error(f"⚠️ Failed to create Square invoice: {str(e)}")

        # Send confirmation email to client
        if client and client.email:
            try:
                # Get business name for client-facing email
                config = (
                    db.query(BusinessConfig)
                    .filter(BusinessConfig.user_id == current_user.id)
                    .first()
                )
                business_name = config.business_name if config else current_user.email

                # Format date properly for email
                formatted_date = schedule.scheduled_date.strftime("%B %d, %Y")
                schedule_time = f"{schedule.start_time} - {schedule.end_time}"

                # Send unified notification (email + SMS) to client
                try:
                    from ..services.notification_service import (
                        send_schedule_confirmation_notification,
                    )

                    await send_schedule_confirmation_notification(
                        db=db,
                        user_id=current_user.id,
                        client_email=client.email,
                        client_phone=client.phone,
                        client_name=client.business_name or client.contact_name or "Client",
                        business_name=business_name,
                        schedule_date=formatted_date,
                        schedule_time=schedule_time,
                    )
                    logger.info(f"✅ Schedule confirmation sent to client: {client.email}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to send confirmation notification to client: {str(e)}")
            except Exception as e:
                logger.error(f"⚠️ Failed to send confirmation to client: {str(e)}")

        # Send confirmation email to provider
        if current_user.email:
            try:
                # Format date properly for email
                formatted_date = schedule.scheduled_date.strftime("%B %d, %Y")

                await email_service.send_schedule_accepted_confirmation_to_provider(
                    provider_email=current_user.email,
                    provider_name=current_user.full_name or "Provider",
                    client_name=client.business_name or client.contact_name or "Client",
                    confirmed_date=formatted_date,
                    confirmed_start_time=schedule.start_time,
                    confirmed_end_time=schedule.end_time,
                    client_address=client.address if hasattr(client, "address") else None,
                )
                logger.info(f"✅ Appointment confirmation sent to provider: {current_user.email}")
            except Exception as e:
                logger.error(f"⚠️ Failed to send confirmation email to provider: {str(e)}")

        return {"message": "Schedule accepted", "schedule_id": schedule_id}

    elif request.action == "request_change":
        # Request alternative date/time
        if not request.proposedDate or not request.proposedStartTime or not request.proposedEndTime:
            raise HTTPException(
                status_code=400, detail="Proposed date and time required for change request"
            )
        schedule.approval_status = "change_requested"
        schedule.proposed_date = request.proposedDate
        schedule.proposed_start_time = request.proposedStartTime
        schedule.proposed_end_time = request.proposedEndTime

        db.commit()

        # Send email to client with proposed alternative
        client = db.query(Client).filter(Client.id == schedule.client_id).first()
        if client and client.email:
            try:
                # Get business name for client-facing email
                config = (
                    db.query(BusinessConfig)
                    .filter(BusinessConfig.user_id == current_user.id)
                    .first()
                )
                business_name = config.business_name if config else current_user.email

                await email_service.send_schedule_change_request(
                    client_email=client.email,
                    client_name=client.business_name or client.contact_name,
                    provider_name=business_name,
                    original_time=schedule.scheduled_date,
                    proposed_time=request.proposedDate,
                    proposed_start=request.proposedStartTime,
                    proposed_end=request.proposedEndTime,
                    schedule_id=schedule_id,
                    client_id=client.id,
                )
            except Exception as e:
                logger.error(f"⚠️ Failed to send change request email: {str(e)}")

        return {
            "message": "Change request sent to client",
            "schedule_id": schedule_id,
            "proposed_date": request.proposedDate.isoformat(),
            "proposed_start_time": request.proposedStartTime,
            "proposed_end_time": request.proposedEndTime,
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


# ============================================
# PUBLIC ENDPOINTS - Client Schedule Response
# ============================================


def generate_schedule_token(schedule_id: int, client_id: int) -> str:
    """Generate a secure token for schedule response links"""
    # Create a deterministic but secure token based on schedule and client IDs
    data = f"{schedule_id}:{client_id}:cleanenroll_schedule_secret"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def verify_schedule_token(schedule_id: int, client_id: int, token: str) -> bool:
    """Verify the schedule response token"""
    expected_token = generate_schedule_token(schedule_id, client_id)
    return secrets.compare_digest(expected_token, token)


class PublicScheduleProposalResponse(BaseModel):
    id: int
    clientName: str
    providerName: str
    originalDate: str
    originalStartTime: str
    originalEndTime: str
    proposedDate: str
    proposedStartTime: str
    proposedEndTime: str
    status: str


class ClientAcceptRequest(BaseModel):
    token: str


class ClientCounterRequest(BaseModel):
    token: str
    preferred_date: str
    preferred_start_time: str
    preferred_end_time: str
    reason: str


@router.get("/public/proposal/{schedule_id}")
async def get_public_schedule_proposal(schedule_id: int, token: str, db: Session = Depends(get_db)):
    """Get schedule proposal details for client response page (public endpoint)"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Verify token
    if not verify_schedule_token(schedule_id, schedule.client_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired link")

    # Only show if there's a pending proposal
    if schedule.approval_status != "change_requested" or not schedule.proposed_date:
        raise HTTPException(status_code=400, detail="No pending proposal for this schedule")

    # Get client and provider info
    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    user = db.query(User).filter(User.id == schedule.user_id).first()

    return PublicScheduleProposalResponse(
        id=schedule.id,
        clientName=client.business_name or client.contact_name if client else "Client",
        providerName=user.full_name or user.email if user else "Service Provider",
        originalDate=schedule.scheduled_date.isoformat() if schedule.scheduled_date else "",
        originalStartTime=schedule.start_time or "",
        originalEndTime=schedule.end_time or "",
        proposedDate=schedule.proposed_date.isoformat() if schedule.proposed_date else "",
        proposedStartTime=schedule.proposed_start_time or "",
        proposedEndTime=schedule.proposed_end_time or "",
        status=schedule.approval_status or "pending",
    )


@router.post("/public/proposal/{schedule_id}/accept")
async def client_accept_proposal(
    schedule_id: int, request: ClientAcceptRequest, db: Session = Depends(get_db)
):
    """Client accepts the provider's proposed alternative time (public endpoint)"""
    from .. import email_service

    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Verify token
    if not verify_schedule_token(schedule_id, schedule.client_id, request.token):
        raise HTTPException(status_code=403, detail="Invalid or expired link")

    # Check if there's a pending proposal
    if schedule.approval_status != "change_requested" or not schedule.proposed_date:
        raise HTTPException(status_code=400, detail="No pending proposal to accept")

    # Update schedule with the proposed time
    schedule.scheduled_date = schedule.proposed_date
    schedule.start_time = schedule.proposed_start_time
    schedule.end_time = schedule.proposed_end_time
    schedule.approval_status = "accepted"

    # Clear the proposal fields
    schedule.proposed_date = None
    schedule.proposed_start_time = None
    schedule.proposed_end_time = None

    # Get client and provider info
    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    user = db.query(User).filter(User.id == schedule.user_id).first()

    # Require a fully signed contract before confirming a schedule.
    contract = (
        db.query(Contract)
        .filter(Contract.client_id == schedule.client_id)
        .order_by(Contract.created_at.desc())
        .first()
    )
    if not contract or contract.status != "signed":
        raise HTTPException(
            status_code=400,
            detail="Contract must be signed by the provider before confirming a schedule.",
        )

    # Do NOT mark the client as scheduled here.
    # At this point the CLIENT accepted the provider's proposal via a public link.
    # The provider must still explicitly accept the schedule in the dashboard.
    # Also, the contract must be signed by the provider before any confirmation.
    #
    # Keep client in pending_approval until provider accepts.
    if client:
        client.status = "pending_approval"

    # Do not mark onboarding completed here.
    # contract.client_onboarding_status remains unchanged until provider accepts.
    # Note: Contract status stays as 'signed' until service starts - client status is separate

    db.commit()
    # Send confirmation email to provider
    if user and user.email:
        try:
            await email_service.send_client_accepted_proposal(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.business_name or client.contact_name if client else "Client",
                accepted_date=schedule.scheduled_date,
                accepted_start_time=schedule.start_time,
                accepted_end_time=schedule.end_time,
                schedule_id=schedule_id,
            )
        except Exception as e:
            logger.error(f"⚠️ Failed to send acceptance email: {str(e)}")

    return {"message": "Proposal accepted", "schedule_id": schedule_id}


@router.post("/public/proposal/{schedule_id}/counter")
async def client_counter_proposal(
    schedule_id: int, request: ClientCounterRequest, db: Session = Depends(get_db)
):
    """Client suggests an alternative time with reason (public endpoint)"""
    from .. import email_service

    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    # Verify token
    if not verify_schedule_token(schedule_id, schedule.client_id, request.token):
        raise HTTPException(status_code=403, detail="Invalid or expired link")

    # Parse the client's preferred date
    try:
        from datetime import datetime as dt

        preferred_date = dt.fromisoformat(request.preferred_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format") from None

    # Update schedule with client's counter-proposal
    # Store in proposed fields (now representing client's suggestion)
    schedule.proposed_date = preferred_date
    schedule.proposed_start_time = request.preferred_start_time
    schedule.proposed_end_time = request.preferred_end_time
    schedule.approval_status = "client_counter"  # New status for client counter-proposal

    # Store the reason in notes (append to existing notes)
    counter_note = f"\n\n--- Client Counter-Proposal ---\nReason: {request.reason}"
    schedule.notes = (schedule.notes or "") + counter_note

    db.commit()

    # Get client and provider info for email
    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    user = db.query(User).filter(User.id == schedule.user_id).first()

    # Send notification email to provider
    if user and user.email:
        try:
            await email_service.send_client_counter_proposal(
                provider_email=user.email,
                provider_name=user.full_name or "Service Provider",
                client_name=client.business_name or client.contact_name if client else "Client",
                original_proposed_date=schedule.scheduled_date,
                client_preferred_date=preferred_date,
                client_preferred_start=request.preferred_start_time,
                client_preferred_end=request.preferred_end_time,
                client_reason=request.reason,
                schedule_id=schedule_id,
            )
        except Exception as e:
            logger.error(f"⚠️ Failed to send counter-proposal email: {str(e)}")

    return {
        "message": "Counter-proposal sent to provider",
        "schedule_id": schedule_id,
        "preferred_date": request.preferred_date,
        "preferred_start_time": request.preferred_start_time,
        "preferred_end_time": request.preferred_end_time,
    }
