"""
Google Calendar Scheduling Routes
Public endpoint for client scheduling via Google Calendar
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Client, GoogleCalendarIntegration, Schedule, User, BusinessConfig
from ..services.google_calendar_service import GoogleCalendarService
from .. import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduling-google-calendar", tags=["scheduling-google-calendar"])
google_calendar_service = GoogleCalendarService()


class SchedulingInfo(BaseModel):
    """Info needed for client scheduling"""
    provider_name: str
    business_name: str
    calendar_connected: bool
    default_duration: int  # in minutes


class TimeSlot(BaseModel):
    """Available time slot"""
    start: datetime
    end: datetime


class AvailableSlots(BaseModel):
    """Available time slots for a date"""
    date: str
    slots: List[TimeSlot]


class ScheduleAppointmentRequest(BaseModel):
    """Request to schedule an appointment"""
    client_id: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


@router.get("/scheduling-info/{client_id}", response_model=SchedulingInfo)
async def get_scheduling_info(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get scheduling info for a client
    
    This is called by the public scheduling page after contract is signed
    """
    try:
        # Get client
        logger.info(f"🔍 Looking up client with ID: {client_id}")
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(f"❌ Client not found: client_id={client_id}")
            raise HTTPException(status_code=404, detail="Client not found")
        
        logger.info(f"✅ Found client {client_id}, user_id={client.user_id}")
        
        # Get service provider's Google Calendar integration
        logger.info(f"🔍 Looking up Google Calendar integration for user_id: {client.user_id}")
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == client.user_id
        ).first()
        
        if not integration:
            logger.error(f"❌ No Google Calendar integration found for user_id={client.user_id}")
            raise HTTPException(
                status_code=404,
                detail="Service provider has not connected Google Calendar"
            )
        
        logger.info(f"✅ Found Google Calendar integration for user {client.user_id}")
        
        return SchedulingInfo(
            provider_name=integration.google_user_email or "Your Service Provider",
            business_name=client.user.business_config.business_name if client.user.business_config else "CleanEnroll",
            calendar_connected=True,
            default_duration=integration.default_appointment_duration or 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting scheduling info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule-appointment")
async def schedule_appointment(
    request: ScheduleAppointmentRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create a Google Calendar appointment for the client
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == request.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get service provider's Google Calendar integration
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == client.user_id
        ).first()
        
        if not integration:
            raise HTTPException(
                status_code=404,
                detail="Service provider has not connected Google Calendar"
            )
        
        # Ensure token is fresh
        from ..routes.google_calendar import _ensure_fresh_token
        access_token = await _ensure_fresh_token(integration, db)
        
        # Prepare event details
        event_summary = f"First Cleaning - {client.business_name or client.contact_name}"
        event_description = f"Initial cleaning appointment for {client.business_name or client.contact_name}"
        
        if request.notes:
            event_description += f"\n\nClient notes: {request.notes}"
        
        # Extract address from form_data JSON field
        client_address = None
        if client.form_data and isinstance(client.form_data, dict):
            client_address = client.form_data.get("address")
        
        # DO NOT create Google Calendar event yet - wait for provider approval
        # Update client with scheduled time
        client.scheduled_start_time = request.start_time
        client.scheduled_end_time = request.end_time
        client.scheduling_status = "pending_approval"
        
        # Create Schedule record with pending approval status
        duration_minutes = int((request.end_time - request.start_time).total_seconds() / 60)
        schedule = Schedule(
            user_id=client.user_id,
            client_id=client.id,
            title=event_summary,
            description=event_description,
            service_type="first_cleaning",
            scheduled_date=request.start_time,
            start_time=request.start_time.strftime("%H:%M"),
            end_time=request.end_time.strftime("%H:%M"),
            duration_minutes=duration_minutes,
            status="scheduled",
            approval_status="pending",  # Requires provider approval
            location=client_address,
            google_calendar_event_id=None,  # Will be set when provider accepts
            notes=request.notes
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        # Send email notification to provider about pending appointment
        provider = db.query(User).filter(User.id == client.user_id).first()
        if provider and provider.email:
            try:
                await email_service.send_appointment_notification(
                    provider_email=provider.email,
                    provider_name=provider.full_name or provider.email,
                    client_name=client.business_name or client.contact_name,
                    appointment_time=request.start_time,
                    location=client_address,
                    event_link=None  # No event link yet, pending approval
                )
                logger.info(f"✅ Sent pending appointment notification to {provider.email}")
            except Exception as e:
                logger.error(f"⚠️ Failed to send email notification: {str(e)}")
                # Don't fail the whole request if email fails
        
        logger.info(f"✅ Created pending schedule for client {request.client_id} - awaiting provider approval")
        
        return {
            "success": True,
            "message": "Appointment request submitted - awaiting provider approval",
            "schedule_id": schedule.id,
            "event_link": event.get("htmlLink"),
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error scheduling appointment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule appointment: {str(e)}")


@router.get("/available-slots/{client_id}")
async def get_available_slots(
    client_id: int,
    date: str,  # Format: YYYY-MM-DD
    db: Session = Depends(get_db)
):
    """
    Get available time slots for a specific date
    This checks the provider's Google Calendar for free/busy times
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get service provider's Google Calendar integration
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == client.user_id
        ).first()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Google Calendar not connected")
        
        # Get provider's availability settings
        business_config = db.query(BusinessConfig).filter(
            BusinessConfig.user_id == client.user_id
        ).first()
        
        # Parse date and check if it's a working day
        target_date = datetime.strptime(date, "%Y-%m-%d")
        day_name = target_date.strftime("%A").lower()
        
        # Check if provider works on this day
        working_days = business_config.working_days if business_config else ["monday", "tuesday", "wednesday", "thursday", "friday"]
        if day_name not in working_days:
            return {"date": date, "slots": [], "duration_minutes": 60, "message": "Provider is not available on this day"}
        
        # Get working hours (default 9 AM - 5 PM)
        working_hours = business_config.working_hours if business_config and business_config.working_hours else {"start": "09:00", "end": "17:00"}
        start_hour, start_minute = map(int, working_hours["start"].split(":"))
        end_hour, end_minute = map(int, working_hours["end"].split(":"))
        
        time_min = target_date.replace(hour=start_hour, minute=start_minute, second=0)
        time_max = target_date.replace(hour=end_hour, minute=end_minute, second=0)
        
        # Get break times if any
        break_times = business_config.break_times if business_config and business_config.break_times else []
        
        # Ensure token is fresh
        from ..routes.google_calendar import _ensure_fresh_token
        access_token = await _ensure_fresh_token(integration, db)
        
        # Get free/busy info
        free_busy = await google_calendar_service.get_free_busy(
            access_token=access_token,
            calendar_id=integration.google_calendar_id,
            time_min=time_min,
            time_max=time_max
        )
        
        # Extract busy periods from Google Calendar
        busy_periods = []
        calendars = free_busy.get("calendars", {})
        calendar_data = calendars.get(integration.google_calendar_id, {})
        busy_times = calendar_data.get("busy", [])
        
        for busy in busy_times:
            start = datetime.fromisoformat(busy["start"].replace('Z', '+00:00'))
            end = datetime.fromisoformat(busy["end"].replace('Z', '+00:00'))
            busy_periods.append({"start": start, "end": end})
        
        # Add break times as busy periods
        for break_time in break_times:
            break_start_hour, break_start_minute = map(int, break_time["start"].split(":"))
            break_end_hour, break_end_minute = map(int, break_time["end"].split(":"))
            break_start = target_date.replace(hour=break_start_hour, minute=break_start_minute, second=0)
            break_end = target_date.replace(hour=break_end_hour, minute=break_end_minute, second=0)
            busy_periods.append({"start": break_start, "end": break_end})
        
        # Generate available slots (1-hour slots)
        duration_minutes = integration.default_appointment_duration or 60
        available_slots = []
        current_time = time_min
        
        while current_time < time_max:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Check if slot overlaps with any busy period
            is_available = True
            for busy in busy_periods:
                if (current_time < busy["end"] and slot_end > busy["start"]):
                    is_available = False
                    break
            
            if is_available and slot_end <= time_max:
                available_slots.append({
                    "start": current_time.isoformat(),
                    "end": slot_end.isoformat()
                })
            
            # Move to next slot (30-minute intervals)
            current_time += timedelta(minutes=30)
        
        return {
            "date": date,
            "slots": available_slots,
            "duration_minutes": duration_minutes
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting available slots: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
