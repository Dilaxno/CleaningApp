"""
Calendly Webhook Routes
Handles incoming webhooks from Calendly for event synchronization
"""

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CalendlyIntegration, Client, Schedule
from ..rate_limiter import create_rate_limiter
from ..webhook_security import verify_calendly_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/calendly", tags=["calendly-webhooks"])

# Rate limiter for webhooks - 100 requests per minute
rate_limit_webhook = create_rate_limiter(
    limit=100,
    window_seconds=60,
    key_prefix="webhook_calendly",
    use_ip=False,  # Global limit for all webhooks
)

CALENDLY_WEBHOOK_SECRET = os.getenv("CALENDLY_WEBHOOK_SECRET")


@router.post("/events")
async def handle_calendly_webhook(
    request: Request, db: Session = Depends(get_db), _: None = Depends(rate_limit_webhook)
):
    """
    Handle Calendly webhook events - Rate limited to 100 requests per minute
    Supported events: invitee.created, invitee.canceled

    Security:
    - Signature verification using HMAC-SHA256
    - Rate limiting to prevent abuse
    """
    try:
        # Verify webhook signature
        if not CALENDLY_WEBHOOK_SECRET:
            logger.warning(
                "⚠️ CALENDLY_WEBHOOK_SECRET not configured - signature verification skipped"
            )
            body = await request.body()
        else:
            is_valid, body = await verify_calendly_webhook(
                request, CALENDLY_WEBHOOK_SECRET, raise_on_failure=True
            )

        # Parse JSON payload
        payload = json.loads(body.decode())

        event_type = payload.get("event")
        event_data = payload.get("payload", {})

        logger.debug(f"📥 Received Calendly webhook: {event_type}")
        logger.debug(f"Webhook payload: {json.dumps(event_data, indent=2)}")

        if event_type == "invitee.created":
            await handle_invitee_created(event_data, db)
        elif event_type == "invitee.canceled":
            await handle_invitee_canceled(event_data, db)
        else:
            # Handle other event types or ignore them
            logger.debug(f"Unhandled event type: {event_type}")

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        logger.exception("Full webhook error traceback:")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def handle_invitee_created(event_data: dict, db: Session):
    """Handle new Calendly booking"""
    try:
        event_uri = event_data.get("event")
        invitee = event_data.get("invitee", {})
        invitee_uri = invitee.get("uri")

        # Extract event details
        start_time_str = event_data.get("start_time")  # ISO 8601 format
        end_time_str = event_data.get("end_time")

        if not start_time_str:
            logger.error("❌ Missing start_time in webhook payload")
            return

        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        end_time = (
            datetime.fromisoformat(end_time_str.replace("Z", "+00:00")) if end_time_str else None
        )

        # Calculate duration
        duration_minutes = None
        if end_time:
            duration_minutes = int((end_time - start_time).total_seconds() / 60)

        # Extract invitee details
        invitee_name = invitee.get("name", "Unknown Client")
        invitee_email = invitee.get("email", "")

        # Try to find the client by email
        client = None
        if invitee_email:
            client = db.query(Client).filter(Client.email == invitee_email).first()

        # Find the service provider by matching calendly_user_uri from event
        # The event URI contains the user's scheduling link
        owner_uri = event_data.get("event_type", {}).get("owner", {}).get("uri")

        if not owner_uri:
            logger.warning("⚠️ Could not determine event owner from webhook")
            return

        integration = (
            db.query(CalendlyIntegration)
            .filter(CalendlyIntegration.calendly_user_uri == owner_uri)
            .first()
        )

        if not integration:
            logger.warning(f"⚠️ No integration found for Calendly user: {owner_uri}")
            return

        # Check if schedule already exists for this event
        existing = db.query(Schedule).filter(Schedule.calendly_event_uri == event_uri).first()

        if existing:
            return

        # Create new schedule entry
        schedule = Schedule(
            user_id=integration.user_id,
            client_id=client.id if client else None,
            title=f"Cleaning Service - {invitee_name}",
            description=f"Booked via Calendly by {invitee_name}",
            service_type="standard",
            scheduled_date=start_time,
            start_time=start_time.strftime("%H:%M"),
            end_time=end_time.strftime("%H:%M") if end_time else None,
            duration_minutes=duration_minutes,
            status="scheduled",
            notes=f"Client email: {invitee_email}",
            calendly_event_uri=event_uri,
            calendly_event_id=event_uri.split("/")[-1] if event_uri else None,
            calendly_invitee_uri=invitee_uri,
            calendly_booking_method="client_selected",
        )

        db.add(schedule)
        db.commit()
        db.refresh(schedule)
    except Exception as e:
        logger.error(f"❌ Error handling invitee.created: {str(e)}")
        logger.exception("Full error traceback:")
        db.rollback()


async def handle_invitee_canceled(event_data: dict, db: Session):
    """Handle Calendly booking cancellation"""
    try:
        event_uri = event_data.get("event")

        if not event_uri:
            logger.error("❌ Missing event URI in cancellation webhook")
            return

        # Find the schedule by Calendly event URI
        schedule = db.query(Schedule).filter(Schedule.calendly_event_uri == event_uri).first()

        if not schedule:
            logger.warning(f"⚠️ No schedule found for cancelled event: {event_uri}")
            return

        # Update schedule status to cancelled
        schedule.status = "cancelled"
        schedule.notes = (
            schedule.notes or ""
        ) + f"\n[Auto-cancelled via Calendly at {datetime.utcnow().isoformat()}]"
        db.commit()
    except Exception as e:
        logger.error(f"❌ Error handling invitee.canceled: {str(e)}")
        logger.exception("Full error traceback:")
        db.rollback()
