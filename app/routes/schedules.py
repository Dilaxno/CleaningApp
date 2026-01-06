import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models import User, Client, Schedule
from ..auth import get_current_user

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
    scheduledDate: datetime
    startTime: Optional[str]
    endTime: Optional[str]
    durationMinutes: Optional[int]
    status: str
    approvalStatus: Optional[str] = "accepted"  # pending, accepted, change_requested
    proposedDate: Optional[datetime] = None
    proposedStartTime: Optional[str] = None
    proposedEndTime: Optional[str] = None
    notes: Optional[str]
    address: Optional[str]
    assignedTo: Optional[str]
    price: Optional[float]
    isRecurring: bool
    recurrencePattern: Optional[str]
    calendlyEventUri: Optional[str]
    calendlyEventId: Optional[str]
    calendlyBookingMethod: Optional[str]
    googleCalendarEventId: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all schedules for the current user"""
    schedules = db.query(Schedule).filter(Schedule.user_id == current_user.id).order_by(Schedule.scheduled_date.asc()).all()
    result = []
    for s in schedules:
        client = db.query(Client).filter(Client.id == s.client_id).first()
        result.append(ScheduleResponse(
            id=s.id,
            clientId=s.client_id,
            clientName=client.business_name if client else "Unknown",
            title=s.title,
            description=s.description,
            serviceType=s.service_type,
            scheduledDate=s.scheduled_date,
            startTime=s.start_time,
            endTime=s.end_time,
            durationMinutes=s.duration_minutes,
            status=s.status,
            notes=s.notes,
            address=s.address,
            assignedTo=s.assigned_to,
            price=s.price,
            isRecurring=s.is_recurring or False,
            recurrencePattern=s.recurrence_pattern,
            calendlyEventUri=s.calendly_event_uri,
            calendlyEventId=s.calendly_event_id,
            calendlyBookingMethod=s.calendly_booking_method,
            createdAt=s.created_at
        ))
    return result


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new schedule"""
    logger.info(f"📥 Creating schedule for user_id: {current_user.id}")
    
    client = db.query(Client).filter(Client.id == data.clientId, Client.user_id == current_user.id).first()
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
        status="scheduled"
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"✅ Schedule created: id={schedule.id}")
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
        createdAt=schedule.created_at
    )


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id).first()
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
        createdAt=schedule.created_at
    )


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept or request change for a pending schedule"""
    from ..models import GoogleCalendarIntegration
    from ..services.google_calendar_service import GoogleCalendarService
    from ..routes.google_calendar import _ensure_fresh_token
    from .. import email_service
    
    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id, 
        Schedule.user_id == current_user.id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if request.action == "accept":
        # Accept the appointment and add to Google Calendar
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == current_user.id
        ).first()
        
        if integration:
            try:
                # Ensure token is fresh
                access_token = await _ensure_fresh_token(integration, db)
                
                # Create Google Calendar event
                google_calendar_service = GoogleCalendarService()
                
                # Combine date and time for datetime object
                start_datetime = schedule.scheduled_date
                end_datetime = schedule.scheduled_date
                
                if schedule.start_time and schedule.end_time:
                    from datetime import time
                    start_parts = schedule.start_time.split(":")
                    end_parts = schedule.end_time.split(":")
                    start_datetime = start_datetime.replace(
                        hour=int(start_parts[0]), 
                        minute=int(start_parts[1])
                    )
                    end_datetime = end_datetime.replace(
                        hour=int(end_parts[0]), 
                        minute=int(end_parts[1])
                    )
                
                client = db.query(Client).filter(Client.id == schedule.client_id).first()
                
                event = await google_calendar_service.create_event(
                    access_token=access_token,
                    calendar_id=integration.google_calendar_id,
                    summary=schedule.title,
                    description=schedule.description,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    attendee_email=client.email if client else None,
                    location=schedule.location
                )
                
                # Update schedule with Google Calendar event ID
                schedule.google_calendar_event_id = event.get("id")
                schedule.approval_status = "accepted"
                
                logger.info(f"✅ Added schedule {schedule_id} to Google Calendar")
                
                # Send confirmation email to client
                if client and client.email:
                    try:
                        await email_service.send_appointment_confirmation(
                            client_email=client.email,
                            client_name=client.business_name or client.contact_name,
                            provider_name=current_user.full_name or current_user.email,
                            appointment_time=start_datetime,
                            location=schedule.location,
                            event_link=event.get("htmlLink")
                        )
                        logger.info(f"✅ Sent confirmation email to client {client.email}")
                    except Exception as e:
                        logger.error(f"⚠️ Failed to send confirmation email: {str(e)}")
                
            except Exception as e:
                logger.error(f"⚠️ Failed to add to Google Calendar: {str(e)}")
                # Still mark as accepted even if calendar sync fails
                schedule.approval_status = "accepted"
        else:
            # No Google Calendar integration, just mark as accepted
            schedule.approval_status = "accepted"
        
        db.commit()
        return {"message": "Schedule accepted", "schedule_id": schedule_id}
    
    elif request.action == "request_change":
        # Request alternative date/time
        if not request.proposedDate or not request.proposedStartTime or not request.proposedEndTime:
            raise HTTPException(
                status_code=400, 
                detail="Proposed date and time required for change request"
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
                await email_service.send_schedule_change_request(
                    client_email=client.email,
                    client_name=client.business_name or client.contact_name,
                    provider_name=current_user.full_name or current_user.email,
                    original_time=schedule.scheduled_date,
                    proposed_time=request.proposedDate,
                    proposed_start=request.proposedStartTime,
                    proposed_end=request.proposedEndTime,
                    schedule_id=schedule_id
                )
                logger.info(f"✅ Sent change request email to client {client.email}")
            except Exception as e:
                logger.error(f"⚠️ Failed to send change request email: {str(e)}")
        
        return {
            "message": "Change request sent to client", 
            "schedule_id": schedule_id,
            "proposed_date": request.proposedDate.isoformat(),
            "proposed_start_time": request.proposedStartTime,
            "proposed_end_time": request.proposedEndTime
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
