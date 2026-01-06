from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..models import User, GoogleCalendarIntegration
from ..services.google_calendar_service import GoogleCalendarService
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-calendar", tags=["google-calendar"])
google_calendar_service = GoogleCalendarService()


class GoogleCalendarOAuthResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleCalendarTokenRequest(BaseModel):
    code: str
    state: str


class GoogleCalendarConnectionStatus(BaseModel):
    connected: bool
    user_email: Optional[str] = None
    calendar_id: Optional[str] = None


@router.get("/connect", response_model=GoogleCalendarOAuthResponse)
async def initiate_google_calendar_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate Google Calendar OAuth flow"""
    state = secrets.token_urlsafe(32)
    
    auth_url = google_calendar_service.get_authorization_url(state)
    
    logger.info(f"🔗 Generated Google Calendar auth URL for user {current_user.id}")
    
    return GoogleCalendarOAuthResponse(
        authorization_url=auth_url,
        state=state
    )


@router.post("/callback")
async def google_calendar_oauth_callback(
    data: GoogleCalendarTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback and store tokens"""
    try:
        logger.info(f"📥 Processing Google Calendar callback for user {current_user.id}")
        
        # Exchange code for tokens
        token_data = await google_calendar_service.exchange_code_for_token(data.code)
        
        # Get user info
        user_info = await google_calendar_service.get_user_info(token_data["access_token"])
        
        # Get primary calendar
        calendar_info = await google_calendar_service.get_primary_calendar(token_data["access_token"])
        
        # Calculate token expiry
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        
        # Check if integration exists
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == current_user.id
        ).first()
        
        if integration:
            # Update existing
            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data.get("refresh_token", integration.refresh_token)
            integration.token_expires_at = expires_at
            integration.google_user_email = user_info.get("email")
            integration.google_calendar_id = calendar_info.get("id")
            logger.info(f"✅ Updated Google Calendar integration for user {current_user.id}")
        else:
            # Create new
            integration = GoogleCalendarIntegration(
                user_id=current_user.id,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_expires_at=expires_at,
                google_user_email=user_info.get("email"),
                google_calendar_id=calendar_info.get("id")
            )
            db.add(integration)
            logger.info(f"✅ Created new Google Calendar integration for user {current_user.id}")
        
        db.commit()
        
        return {
            "message": "Google Calendar connected successfully",
            "email": user_info.get("email")
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to connect Google Calendar for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect Google Calendar: {str(e)}")


async def _ensure_fresh_token(integration: GoogleCalendarIntegration, db: Session) -> str:
    """Ensure access token is fresh, refresh if needed"""
    if datetime.utcnow() >= integration.token_expires_at - timedelta(minutes=5):
        logger.info(f"🔄 Refreshing Google Calendar token for user {integration.user_id}")
        try:
            token_data = await google_calendar_service.refresh_access_token(integration.refresh_token)
            integration.access_token = token_data["access_token"]
            integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
            db.commit()
            logger.info(f"✅ Token refreshed for user {integration.user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to refresh token for user {integration.user_id}: {str(e)}")
            raise HTTPException(status_code=401, detail="Google Calendar token expired. Please reconnect.")
    
    return integration.access_token


@router.get("/status", response_model=GoogleCalendarConnectionStatus)
async def get_google_calendar_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Google Calendar connection status"""
    integration = db.query(GoogleCalendarIntegration).filter(
        GoogleCalendarIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        return GoogleCalendarConnectionStatus(connected=False)
    
    return GoogleCalendarConnectionStatus(
        connected=True,
        user_email=integration.google_user_email,
        calendar_id=integration.google_calendar_id
    )


@router.post("/disconnect")
async def disconnect_google_calendar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Google Calendar integration"""
    integration = db.query(GoogleCalendarIntegration).filter(
        GoogleCalendarIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="No Google Calendar integration found")
    
    db.delete(integration)
    db.commit()
    
    logger.info(f"🔌 Disconnected Google Calendar for user {current_user.id}")
    
    return {"message": "Google Calendar disconnected successfully"}


@router.post("/create-event")
async def create_calendar_event(
    client_id: int,
    start_time: datetime,
    end_time: datetime,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a calendar event for a client appointment"""
    from ..models import Client
    
    integration = db.query(GoogleCalendarIntegration).filter(
        GoogleCalendarIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Google Calendar not connected")
    
    # Get client info
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)
    
    # Create event
    try:
        event = await google_calendar_service.create_event(
            access_token=access_token,
            calendar_id=integration.google_calendar_id,
            summary=f"Cleaning Appointment - {client.business_name or client.contact_name}",
            description=f"First cleaning appointment for {client.business_name or client.contact_name}",
            start_time=start_time,
            end_time=end_time,
            attendee_email=client.email,
            location=client.address
        )
        
        logger.info(f"✅ Created calendar event for client {client_id}")
        
        return {
            "message": "Event created successfully",
            "event_id": event.get("id"),
            "event_link": event.get("htmlLink")
        }
    except Exception as e:
        logger.error(f"❌ Failed to create event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


@router.get("/events")
async def get_upcoming_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get upcoming events from Google Calendar"""
    integration = db.query(GoogleCalendarIntegration).filter(
        GoogleCalendarIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Google Calendar not connected")
    
    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)
    
    # Get events from now onwards
    try:
        events = await google_calendar_service.list_events(
            access_token=access_token,
            calendar_id=integration.google_calendar_id,
            time_min=datetime.utcnow()
        )
        
        return events
    except Exception as e:
        logger.error(f"❌ Failed to get events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")
