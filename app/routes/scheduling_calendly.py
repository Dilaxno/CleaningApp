"""
Calendly Scheduling Routes
Public endpoint for client scheduling via Calendly
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CalendlyIntegration, Client
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
async def get_booking_info(client_id: int, db: Session = Depends(get_db)):
    """
    Get Calendly booking URL for a client to schedule an appointment

    This is called by the public ScheduleSelection page after contract is signed
    """
    try:
        # Get client
        logger.info(f"🔍 Looking up client with ID: {client_id}")
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(f"❌ Client not found: client_id={client_id}")
            raise HTTPException(status_code=404, detail="Client not found")
        # Get service provider's Calendly integration
        logger.info(f"🔍 Looking up Calendly integration for user_id: {client.user_id}")
        integration = (
            db.query(CalendlyIntegration)
            .filter(CalendlyIntegration.user_id == client.user_id)
            .first()
        )

        if not integration:
            logger.error(f"❌ No Calendly integration found for user_id={client.user_id}")
            raise HTTPException(
                status_code=404, detail="Service provider has not connected Calendly"
            )
        if not integration.default_event_type_url:
            logger.error(
                f"❌ Calendly integration exists but default_event_type_url is not set for user_id={client.user_id}"
            )
            raise HTTPException(
                status_code=404, detail="Service provider has not configured a default event type"
            )

        # Generate scheduling link with prefilled client info
        prefill_data = {
            "name": client.contact_name or client.business_name,
            "email": client.email or "",
        }

        booking_url = calendly_service.generate_scheduling_link(
            integration.default_event_type_url, prefill_data
        )
        return CalendlyBookingInfo(
            booking_url=booking_url,
            provider_name=integration.calendly_user_email or "Your Service Provider",
            business_name=(
                client.user.business_config.business_name
                if client.user.business_config
                else "CleanEnroll"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting booking info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/client-preferences/{client_id}")
async def get_client_preferences(client_id: int, db: Session = Depends(get_db)):
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
            "notes": form_data.get("scheduleNotes", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting client preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/webhook")
async def calendly_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Calendly to notify when a client books an appointment
    This captures the client's preferred cleaning time for provider review
    """
    try:
        payload = await request.json()
        logger.info(f"📅 Received Calendly webhook: {payload.get('event')}")

        event_type = payload.get("event")

        # Handle event.created (when client books a time)
        if event_type == "invitee.created":
            event_data = payload.get("payload", {})
            event_obj = event_data.get("event", {})
            invitee = event_data.get("invitee", {})

            # Extract event details
            start_time_str = event_obj.get("start_time")
            end_time_str = event_obj.get("end_time")
            event_id = event_obj.get("uuid")
            invitee_email = invitee.get("email")

            if not all([start_time_str, end_time_str, invitee_email]):
                logger.warning("⚠️ Missing required fields in Calendly webhook")
                return {"status": "ignored", "reason": "missing_fields"}

            # Parse times
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))

            # Find client by email
            client = db.query(Client).filter(Client.email == invitee_email).first()

            if client:
                # Update client with scheduled time
                client.scheduled_start_time = start_time
                client.scheduled_end_time = end_time
                client.calendly_event_id = event_id
                client.scheduling_status = "client_selected"

                db.commit()
                # TODO: Send notification to provider about client's selected time

                return {
                    "status": "success",
                    "client_id": client.id,
                    "scheduled_time": start_time_str,
                }
            else:
                logger.warning(f"⚠️ No client found with email {invitee_email}")
                return {"status": "ignored", "reason": "client_not_found"}

        # Handle event.cancelled
        elif event_type == "invitee.canceled":
            event_data = payload.get("payload", {})
            invitee = event_data.get("invitee", {})
            invitee_email = invitee.get("email")

            client = db.query(Client).filter(Client.email == invitee_email).first()
            if client:
                client.scheduled_start_time = None
                client.scheduled_end_time = None
                client.calendly_event_id = None
                client.scheduling_status = "pending"
                db.commit()
                return {"status": "success", "action": "cleared"}

        return {"status": "success", "event": event_type}

    except Exception as e:
        logger.error(f"❌ Error processing Calendly webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
