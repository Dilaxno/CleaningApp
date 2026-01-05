"""
Calendly Scheduling Routes
Public endpoint for client scheduling via Calendly
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models import Client, CalendlyIntegration
from ..services.calendly_service import CalendlyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduling-calendly", tags=["scheduling-calendly"])
calendly_service = CalendlyService()


class CalendlyBookingInfo(BaseModel):
    """Info needed for Calendly booking widget"""
    booking_url: str
    provider_name: str
    business_name: str


@router.get("/booking-info/{client_id}", response_model=CalendlyBookingInfo)
async def get_booking_info(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get Calendly booking URL for a client to schedule an appointment
    
    This is called by the public ScheduleSelection page after contract is signed
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get service provider's Calendly integration
        integration = db.query(CalendlyIntegration).filter(
            CalendlyIntegration.user_id == client.user_id
        ).first()
        
        if not integration:
            raise HTTPException(
                status_code=404,
                detail="Service provider has not connected Calendly"
            )
        
        if not integration.default_event_type_url:
            raise HTTPException(
                status_code=404,
                detail="Service provider has not configured a default event type"
            )
        
        # Generate scheduling link with prefilled client info
        prefill_data = {
            "name": client.contact_name or client.business_name,
            "email": client.email or "",
        }
        
        booking_url = calendly_service.generate_scheduling_link(
            integration.default_event_type_url,
            prefill_data
        )
        
        logger.info(f"📅 Generated Calendly booking URL for client {client_id}")
        
        return CalendlyBookingInfo(
            booking_url=booking_url,
            provider_name=integration.calendly_user_email or "Your Service Provider",
            business_name=client.user.business_config.business_name if client.user.business_config else "CleanEnroll"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting booking info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client-preferences/{client_id}")
async def get_client_preferences(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get client's scheduling preferences from their form submission
    Used to highlight preferred times in Calendly widget
    """
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Extract preferences from form_data
        form_data = client.form_data or {}
        
        # Look for time preference fields
        preferred_days = form_data.get("preferredDays", [])
        preferred_time = form_data.get("preferredTime", "")
        time_window_start = form_data.get("preferredTimeStart", "")
        time_window_end = form_data.get("preferredTimeEnd", "")
        
        return {
            "client_id": client_id,
            "preferred_days": preferred_days if isinstance(preferred_days, list) else [],
            "preferred_time": preferred_time,
            "time_window_start": time_window_start,
            "time_window_end": time_window_end,
            "notes": form_data.get("scheduleNotes", "")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting client preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
