"""
Calendly Webhook Routes
Handles incoming webhooks from Calendly for event synchronization
"""
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import Schedule, CalendlyIntegration, Client
import hmac
import hashlib
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/calendly", tags=["calendly-webhooks"])

CALENDLY_WEBHOOK_SECRET = os.getenv("CALENDLY_WEBHOOK_SECRET")


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Calendly webhook signature"""
    if not CALENDLY_WEBHOOK_SECRET:
        logger.warning("⚠️ CALENDLY_WEBHOOK_SECRET not configured - skipping signature verification")
        return True
    
    expected_signature = hmac.new(
        CALENDLY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)


@router.post("/events")
async def handle_calendly_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Calendly webhook events
    Supported events: invitee.created, invitee.canceled
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        signature = request.headers.get("Calendly-Webhook-Signature", "")
        
        # Verify signature
        if not verify_webhook_signature(body, signature):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse JSON payload
        import json
        payload = json.loads(body.decode())
        
        event_type = payload.get("event")
        event_data = payload.get("payload", {})
        
        logger.info(f"📥 Received Calendly webhook: {event_type}")
        logger.debug(f"Webhook payload: {json.dumps(event_data, indent=2)}")
        
        if event_type == "invitee.created":
            await handle_invitee_created(event_data, db)
        elif event_type == "invitee.canceled":
            await handle_invitee_canceled(event_data, db)
        else:
            logger.info(f"ℹ️ Unhandled event type: {event_type}")
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        logger.exception("Full webhook error traceback:")
        raise HTTPException(status_code=500, detail=str(e))


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
        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00")) if end_time_str else None
        
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
        
        integration = db.query(CalendlyIntegration).filter(
            CalendlyIntegration.calendly_user_uri == owner_uri
        ).first()
        
        if not integration:
            logger.warning(f"⚠️ No integration found for Calendly user: {owner_uri}")
            return
        
        # Check if schedule already exists for this event
        existing = db.query(Schedule).filter(
            Schedule.calendly_event_uri == event_uri
        ).first()
        
        if existing:
            logger.info(f"ℹ️ Schedule already exists for event: {event_uri}")
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
            calendly_booking_method="client_selected"
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"✅ Created schedule from Calendly booking: ID={schedule.id}, Event={event_uri}")
    
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
        schedule = db.query(Schedule).filter(
            Schedule.calendly_event_uri == event_uri
        ).first()
        
        if not schedule:
            logger.warning(f"⚠️ No schedule found for cancelled event: {event_uri}")
            return
        
        # Update schedule status to cancelled
        schedule.status = "cancelled"
        schedule.notes = (schedule.notes or "") + f"\n[Auto-cancelled via Calendly at {datetime.utcnow().isoformat()}]"
        db.commit()
        
        logger.info(f"✅ Cancelled schedule from Calendly: ID={schedule.id}, Event={event_uri}")
    
    except Exception as e:
        logger.error(f"❌ Error handling invitee.canceled: {str(e)}")
        logger.exception("Full error traceback:")
        db.rollback()
