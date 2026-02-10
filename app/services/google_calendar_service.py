"""
Google Calendar Service
Handles calendar event creation, updates, and deletion
"""
import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from ..models import User, Schedule
from ..models_google_calendar import GoogleCalendarIntegration
from ..config import SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


async def get_valid_access_token(integration: GoogleCalendarIntegration, db: Session) -> Optional[str]:
    """
    Get a valid access token, refreshing if necessary
    Returns None if refresh fails
    """
    try:
        # Check if token is expired or about to expire (within 5 minutes)
        if integration.token_expires_at <= datetime.utcnow() + timedelta(minutes=5):
            logger.info("🔄 Google Calendar token expired, refreshing...")
            
            # Decrypt refresh token
            cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b'='))
            refresh_token = cipher_suite.decrypt(integration.refresh_token.encode()).decode()
            
            # Request new access token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ Token refresh failed: {response.text}")
                    return None
                
                tokens = response.json()
                new_access_token = tokens.get("access_token")
                expires_in = tokens.get("expires_in", 3600)
                
                if not new_access_token:
                    logger.error("❌ No access token in refresh response")
                    return None
                
                # Encrypt and save new access token
                encrypted_access_token = cipher_suite.encrypt(new_access_token.encode()).decode()
                integration.access_token = encrypted_access_token
                integration.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                db.commit()
                
                logger.info("✅ Google Calendar token refreshed successfully")
                return new_access_token
        else:
            # Token still valid, decrypt and return
            cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b'='))
            access_token = cipher_suite.decrypt(integration.access_token.encode()).decode()
            return access_token
            
    except Exception as e:
        logger.error(f"❌ Error getting valid access token: {str(e)}")
        return None


async def create_calendar_event(
    user: User,
    schedule: Schedule,
    db: Session
) -> Optional[str]:
    """
    Create a Google Calendar event for a schedule
    Returns the Google Calendar event ID if successful, None otherwise
    """
    try:
        # Get integration
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == user.id
        ).first()
        
        if not integration or not integration.auto_sync_enabled:
            logger.info("ℹ️ Google Calendar not connected or auto-sync disabled")
            return None
        
        # Get valid access token
        access_token = await get_valid_access_token(integration, db)
        if not access_token:
            logger.error("❌ Failed to get valid access token")
            return None
        
        # Build event data
        # Parse start time from schedule
        if schedule.start_time:
            # Parse the start time (format: "HH:MM" or "HH:MM AM/PM")
            from datetime import time as dt_time
            start_time_str = schedule.start_time.strip()
            
            # Handle both 24h and 12h formats
            try:
                # Try 24h format first (HH:MM)
                start_parts = start_time_str.split(":")
                start_hour = int(start_parts[0])
                start_min = int(start_parts[1].split()[0])  # Remove AM/PM if present
                start_time = dt_time(start_hour, start_min)
            except (ValueError, IndexError):
                # Try 12h format (HH:MM AM/PM)
                from datetime import datetime as dt
                start_time = dt.strptime(start_time_str, "%I:%M %p").time()
            
            # Combine date with parsed time
            start_datetime = datetime.combine(schedule.scheduled_date.date(), start_time)
        else:
            # No start time specified, use date at midnight
            start_datetime = schedule.scheduled_date
        
        # Calculate end time
        if schedule.duration_minutes and schedule.start_time:
            # Use duration from start time
            end_datetime = start_datetime + timedelta(minutes=schedule.duration_minutes)
        elif schedule.end_time:
            # Parse end time
            from datetime import time as dt_time
            end_time_str = schedule.end_time.strip()
            
            try:
                # Try 24h format first
                end_parts = end_time_str.split(":")
                end_hour = int(end_parts[0])
                end_min = int(end_parts[1].split()[0])
                end_time = dt_time(end_hour, end_min)
            except (ValueError, IndexError):
                # Try 12h format
                from datetime import datetime as dt
                end_time = dt.strptime(end_time_str, "%I:%M %p").time()
            
            end_datetime = datetime.combine(schedule.scheduled_date.date(), end_time)
        else:
            # Default 1 hour duration
            end_datetime = start_datetime + timedelta(hours=1)
        
        # Get client info for event details
        from ..models import Client
        client = db.query(Client).filter(Client.id == schedule.client_id).first()
        client_name = client.business_name if client else "Client"
        
        event_data = {
            "summary": f"{schedule.title} - {client_name}",
            "description": schedule.description or f"Service appointment with {client_name}",
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "UTC"
            }
        }
        
        # Add location if available
        if schedule.address:
            event_data["location"] = schedule.address
        
        # Add notes to description
        if schedule.notes:
            event_data["description"] += f"\n\nNotes: {schedule.notes}"
        
        # Create event in Google Calendar
        calendar_id = integration.google_calendar_id or "primary"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ Failed to create calendar event: {response.text}")
                return None
            
            event = response.json()
            event_id = event.get("id")
            
            logger.info(f"✅ Google Calendar event created: {event_id}")
            return event_id
            
    except Exception as e:
        logger.error(f"❌ Error creating calendar event: {str(e)}")
        return None


async def update_calendar_event(
    user: User,
    schedule: Schedule,
    google_event_id: str,
    db: Session
) -> bool:
    """
    Update an existing Google Calendar event
    Returns True if successful, False otherwise
    """
    try:
        # Get integration
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == user.id
        ).first()
        
        if not integration or not integration.auto_sync_enabled:
            logger.info("ℹ️ Google Calendar not connected or auto-sync disabled")
            return False
        
        # Get valid access token
        access_token = await get_valid_access_token(integration, db)
        if not access_token:
            logger.error("❌ Failed to get valid access token")
            return False
        
        # Build updated event data
        # Parse start time from schedule
        if schedule.start_time:
            # Parse the start time (format: "HH:MM" or "HH:MM AM/PM")
            from datetime import time as dt_time
            start_time_str = schedule.start_time.strip()
            
            # Handle both 24h and 12h formats
            try:
                # Try 24h format first (HH:MM)
                start_parts = start_time_str.split(":")
                start_hour = int(start_parts[0])
                start_min = int(start_parts[1].split()[0])  # Remove AM/PM if present
                start_time = dt_time(start_hour, start_min)
            except (ValueError, IndexError):
                # Try 12h format (HH:MM AM/PM)
                from datetime import datetime as dt
                start_time = dt.strptime(start_time_str, "%I:%M %p").time()
            
            # Combine date with parsed time
            start_datetime = datetime.combine(schedule.scheduled_date.date(), start_time)
        else:
            # No start time specified, use date at midnight
            start_datetime = schedule.scheduled_date
        
        # Calculate end time
        if schedule.duration_minutes and schedule.start_time:
            # Use duration from start time
            end_datetime = start_datetime + timedelta(minutes=schedule.duration_minutes)
        elif schedule.end_time:
            # Parse end time
            from datetime import time as dt_time
            end_time_str = schedule.end_time.strip()
            
            try:
                # Try 24h format first
                end_parts = end_time_str.split(":")
                end_hour = int(end_parts[0])
                end_min = int(end_parts[1].split()[0])
                end_time = dt_time(end_hour, end_min)
            except (ValueError, IndexError):
                # Try 12h format
                from datetime import datetime as dt
                end_time = dt.strptime(end_time_str, "%I:%M %p").time()
            
            end_datetime = datetime.combine(schedule.scheduled_date.date(), end_time)
        else:
            # Default 1 hour duration
            end_datetime = start_datetime + timedelta(hours=1)
        
        # Get client info
        from ..models import Client
        client = db.query(Client).filter(Client.id == schedule.client_id).first()
        client_name = client.business_name if client else "Client"
        
        event_data = {
            "summary": f"{schedule.title} - {client_name}",
            "description": schedule.description or f"Service appointment with {client_name}",
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "UTC"
            }
        }
        
        if schedule.address:
            event_data["location"] = schedule.address
        
        if schedule.notes:
            event_data["description"] += f"\n\nNotes: {schedule.notes}"
        
        # Update event in Google Calendar
        calendar_id = integration.google_calendar_id or "primary"
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to update calendar event: {response.text}")
                return False
            
            logger.info(f"✅ Google Calendar event updated: {google_event_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error updating calendar event: {str(e)}")
        return False


async def delete_calendar_event(
    user: User,
    google_event_id: str,
    db: Session
) -> bool:
    """
    Delete a Google Calendar event
    Returns True if successful, False otherwise
    """
    try:
        # Get integration
        integration = db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == user.id
        ).first()
        
        if not integration:
            logger.info("ℹ️ Google Calendar not connected")
            return False
        
        # Get valid access token
        access_token = await get_valid_access_token(integration, db)
        if not access_token:
            logger.error("❌ Failed to get valid access token")
            return False
        
        # Delete event from Google Calendar
        calendar_id = integration.google_calendar_id or "primary"
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code not in [200, 204]:
                logger.error(f"❌ Failed to delete calendar event: {response.text}")
                return False
            
            logger.info(f"✅ Google Calendar event deleted: {google_event_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error deleting calendar event: {str(e)}")
        return False
