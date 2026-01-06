import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode
from ..config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Service for interacting with Google Calendar API"""
    
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
    
    def get_authorization_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL"""
        scope = " ".join(self.SCOPES)
        
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Force consent screen to get refresh token
            "state": state
        }
        
        query_string = urlencode(params)
        auth_url = f"{self.AUTH_URL}?{query_string}"
        
        logger.info(f"🔗 Generating authorization URL with redirect_uri: {GOOGLE_REDIRECT_URI}")
        logger.info(f"🔗 Full auth URL: {auth_url}")
        
        return auth_url
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        logger.info(f"🔄 Exchanging OAuth code for token with redirect_uri: {GOOGLE_REDIRECT_URI}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Token exchange failed: {response.text}")
                raise Exception(f"Token exchange failed: {response.text}")
            
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        logger.info("🔄 Refreshing Google Calendar access token")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "grant_type": "refresh_token"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Token refresh failed: {response.text}")
                raise Exception(f"Token refresh failed: {response.text}")
            
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get user info: {response.text}")
                raise Exception(f"Failed to get user info: {response.text}")
            
            return response.json()
    
    async def get_primary_calendar(self, access_token: str) -> Dict[str, Any]:
        """Get user's primary calendar"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.CALENDAR_API_BASE}/users/me/calendarList/primary",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get primary calendar: {response.text}")
                raise Exception(f"Failed to get primary calendar: {response.text}")
            
            return response.json()
    
    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendee_email: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a calendar event"""
        event_data = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "UTC"
            }
        }
        
        if location:
            event_data["location"] = location
        
        if attendee_email:
            event_data["attendees"] = [{"email": attendee_email}]
            event_data["sendUpdates"] = "all"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=event_data
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ Failed to create event: {response.text}")
                raise Exception(f"Failed to create event: {response.text}")
            
            return response.json()
    
    async def list_events(
        self,
        access_token: str,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """List calendar events"""
        params = {
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime"
        }
        
        if time_min:
            params["timeMin"] = time_min.isoformat() + "Z"
        
        if time_max:
            params["timeMax"] = time_max.isoformat() + "Z"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to list events: {response.text}")
                raise Exception(f"Failed to list events: {response.text}")
            
            return response.json()
    
    async def get_free_busy(
        self,
        access_token: str,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime
    ) -> Dict[str, Any]:
        """Get free/busy information for a calendar"""
        request_body = {
            "timeMin": time_min.isoformat() + "Z",
            "timeMax": time_max.isoformat() + "Z",
            "items": [{"id": calendar_id}]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.CALENDAR_API_BASE}/freeBusy",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get free/busy: {response.text}")
                raise Exception(f"Failed to get free/busy: {response.text}")
            
            return response.json()
