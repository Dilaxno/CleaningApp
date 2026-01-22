import httpx
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ZohoBookingService:
    """Service for interacting with Zoho Booking API"""
    
    BASE_URL = "https://bookings.zoho.com/api/v1"
    AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
    TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
    
    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZOHO_REDIRECT_URI")
        self.scope = "ZohoBookings.fullaccess.all"
    
    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL"""
        if not self.redirect_uri:
            logger.error("ZOHO_REDIRECT_URI not configured in environment variables")
            raise ValueError("Zoho redirect URI not configured")
        
        logger.info(f"🔗 Generating Zoho authorization URL with redirect_uri: {self.redirect_uri}")
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": self.scope,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "access_type": "offline"
        }
        from urllib.parse import urlencode
        query = urlencode(params)
        auth_url = f"{self.AUTH_URL}?{query}"
        logger.info(f"🔗 Full Zoho auth URL: {auth_url}")
        return auth_url
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri
            }
            
            logger.info(f"🔄 Exchanging Zoho OAuth code for token with redirect_uri: {self.redirect_uri}")
            
            response = await client.post(
                self.TOKEN_URL,
                data=payload
            )
            
            if response.status_code != 200:
                error_body = response.text
                logger.error(f"❌ Zoho token exchange failed: {response.status_code}")
                logger.error(f"❌ Error response: {error_body}")
                logger.error(f"❌ Redirect URI sent: {self.redirect_uri}")
            
            response.raise_for_status()
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh expired access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get current user information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/user",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def list_workspaces(self, access_token: str) -> Dict[str, Any]:
        """List user's workspaces"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/workspaces",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def list_services(self, access_token: str, workspace_id: str) -> Dict[str, Any]:
        """List services in a workspace"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/workspaces/{workspace_id}/services",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def create_service(
        self, 
        access_token: str, 
        workspace_id: str, 
        service_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new service in workspace"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/workspaces/{workspace_id}/services",
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json"
                },
                json=service_data
            )
            response.raise_for_status()
            return response.json()
    
    async def get_bookings(
        self, 
        access_token: str, 
        workspace_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get bookings for a workspace"""
        params = {}
        if from_date:
            params["from_date"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to_date"] = to_date.strftime("%Y-%m-%d")
        if status:
            params["status"] = status
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/workspaces/{workspace_id}/bookings",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def create_booking(
        self, 
        access_token: str, 
        workspace_id: str, 
        booking_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new booking"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/workspaces/{workspace_id}/bookings",
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json"
                },
                json=booking_data
            )
            response.raise_for_status()
            return response.json()
    
    async def cancel_booking(
        self, 
        access_token: str, 
        workspace_id: str, 
        booking_id: str, 
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel a booking"""
        data = {"status": "cancelled"}
        if reason:
            data["cancellation_reason"] = reason
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/workspaces/{workspace_id}/bookings/{booking_id}",
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    def generate_booking_link(
        self, 
        workspace_id: str, 
        service_id: str, 
        prefill_data: Optional[Dict] = None
    ) -> str:
        """
        Generate a booking link for clients
        
        Args:
            workspace_id: Zoho workspace ID
            service_id: Service ID for cleaning appointments
            prefill_data: Optional dict with 'name', 'email', 'phone' for prefilling
        
        Returns:
            Complete booking URL with prefilled parameters
        """
        base_url = f"https://bookings.zoho.com/portal/{workspace_id}/service/{service_id}"
        
        if not prefill_data:
            return base_url
        
        # Zoho Booking supports URL parameters for prefilling
        params = []
        if prefill_data.get("name"):
            params.append(f"customer_name={prefill_data['name']}")
        if prefill_data.get("email"):
            params.append(f"customer_email={prefill_data['email']}")
        if prefill_data.get("phone"):
            params.append(f"customer_phone={prefill_data['phone']}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        
        return base_url
    
    def generate_public_booking_link(
        self, 
        workspace_id: str, 
        service_id: str, 
        client_data: Optional[Dict] = None
    ) -> str:
        """
        Generate a public booking link for clients with business branding
        
        Args:
            workspace_id: Zoho workspace ID
            service_id: Service ID for cleaning appointments
            client_data: Optional dict with client information for prefilling
        
        Returns:
            Complete public booking URL
        """
        # Use the public booking portal URL
        base_url = f"https://bookings.zoho.com/portal/{workspace_id}"
        
        # If specific service, link directly to it
        if service_id:
            base_url = f"{base_url}/service/{service_id}"
        
        # Add client prefill data if available
        if client_data:
            params = []
            if client_data.get("name"):
                params.append(f"name={client_data['name']}")
            if client_data.get("email"):
                params.append(f"email={client_data['email']}")
            if client_data.get("phone"):
                params.append(f"phone={client_data['phone']}")
            
            if params:
                separator = "?" if "?" not in base_url else "&"
                base_url = f"{base_url}{separator}{'&'.join(params)}"
        
        return base_url
    
    async def setup_webhook(
        self, 
        access_token: str, 
        workspace_id: str, 
        webhook_url: str, 
        events: List[str]
    ) -> Dict[str, Any]:
        """
        Set up webhook for booking events
        
        Args:
            access_token: Zoho access token
            workspace_id: Workspace ID
            webhook_url: Your webhook endpoint URL
            events: List of events to subscribe to (e.g., ['booking.created', 'booking.cancelled'])
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/workspaces/{workspace_id}/webhooks",
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": webhook_url,
                    "events": events,
                    "status": "active"
                }
            )
            response.raise_for_status()
            return response.json()