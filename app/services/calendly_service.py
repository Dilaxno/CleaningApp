import logging
import os
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class CalendlyService:
    """Service for interacting with Calendly API"""

    BASE_URL = "https://api.calendly.com"
    AUTH_URL = "https://auth.calendly.com/oauth/authorize"
    TOKEN_URL = "https://auth.calendly.com/oauth/token"  # noqa: S105 - OAuth endpoint URL

    def __init__(self):
        self.client_id = os.getenv("CALENDLY_CLIENT_ID")
        self.client_secret = os.getenv("CALENDLY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CALENDLY_REDIRECT_URI")

    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL"""
        if not self.redirect_uri:
            logger.error("CALENDLY_REDIRECT_URI not configured in environment variables")
            raise ValueError("Calendly redirect URI not configured")

        logger.info(f"🔗 Generating authorization URL with redirect_uri: {self.redirect_uri}")

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "default",  # Add default scope which includes event management permissions
        }
        from urllib.parse import urlencode

        query = urlencode(params)
        auth_url = f"{self.AUTH_URL}?{query}"
        logger.info(f"🔗 Full auth URL: {auth_url}")
        return auth_url

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            }

            logger.info(
                f"🔄 Exchanging OAuth code for token with redirect_uri: {self.redirect_uri}"
            )

            response = await client.post(self.TOKEN_URL, data=payload)

            if response.status_code != 200:
                error_body = response.text
                logger.error(f"❌ Calendly token exchange failed: {response.status_code}")
                logger.error(f"❌ Error response: {error_body}")
                logger.error(f"❌ Redirect URI sent: {self.redirect_uri}")

            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh expired access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get current user information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/users/me", headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()

    async def list_event_types(self, access_token: str, user_uri: str) -> dict[str, Any]:
        """List user's event types"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/event_types",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"user": user_uri},
            )
            response.raise_for_status()
            return response.json()

    async def get_scheduled_events(
        self,
        access_token: str,
        user_uri: str,
        min_start_time: Optional[datetime] = None,
        max_start_time: Optional[datetime] = None,
        count: int = 100,
    ) -> dict[str, Any]:
        """Get scheduled events for a user"""
        params = {"user": user_uri, "count": count}

        if min_start_time:
            params["min_start_time"] = min_start_time.isoformat()
        if max_start_time:
            params["max_start_time"] = max_start_time.isoformat()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/scheduled_events",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_event_invitees(self, access_token: str, event_uuid: str) -> dict[str, Any]:
        """Get invitees for a scheduled event"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/scheduled_events/{event_uuid}/invitees",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def cancel_event(
        self, access_token: str, event_uuid: str, reason: Optional[str] = None
    ) -> None:
        """Cancel a scheduled event"""
        data = {}
        if reason:
            data["reason"] = reason

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"🗑️ Attempting to cancel Calendly event {event_uuid}")
                response = await client.post(
                    f"{self.BASE_URL}/scheduled_events/{event_uuid}/cancellation",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=data,
                )

                if response.status_code == 403:
                    logger.error(
                        f"❌ 403 Forbidden when cancelling event {event_uuid}. This could mean:"
                    )
                    logger.error("   - The OAuth token doesn't have sufficient permissions")
                    logger.error("   - The user is not the owner of this event")
                    logger.error(
                        "   - The event is already cancelled or in a non-cancellable state"
                    )
                    raise httpx.HTTPStatusError(
                        "Permission denied. You may not be the owner of this event or it may already be cancelled.",
                        request=response.request,
                        response=response,
                    )
                elif response.status_code == 404:
                    logger.error(
                        f"❌ 404 Not Found when cancelling event {event_uuid}. Event may not exist or UUID is incorrect."
                    )
                    raise httpx.HTTPStatusError(
                        "Event not found. The event may have already been cancelled or the ID is incorrect.",
                        request=response.request,
                        response=response,
                    )
                elif response.status_code == 401:
                    logger.error(
                        f"❌ 401 Unauthorized when cancelling event {event_uuid}. Token may be expired."
                    )
                    raise httpx.HTTPStatusError(
                        "Authentication failed. Please reconnect your Calendly account.",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()
                logger.info(f"✅ Successfully cancelled Calendly event {event_uuid}")

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ HTTP error cancelling event {event_uuid}: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error cancelling event {event_uuid}: {e}")
                raise

    async def get_event_details(self, access_token: str, event_uuid: str) -> dict[str, Any]:
        """Get details of a scheduled event"""
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"📋 Fetching details for Calendly event {event_uuid}")
                response = await client.get(
                    f"{self.BASE_URL}/scheduled_events/{event_uuid}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Failed to get event details for {event_uuid}: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error getting event details for {event_uuid}: {e}")
                raise

    def generate_scheduling_link(
        self, event_type_url: str, prefill_data: Optional[dict] = None
    ) -> str:
        """
        Generate a scheduling link with prefilled data

        Args:
            event_type_url: The Calendly event type scheduling URL
            prefill_data: Optional dict with 'name', 'email', 'phone' for prefilling

        Returns:
            Complete scheduling URL with prefilled parameters
        """
        if not prefill_data:
            return event_type_url

        # Calendly supports URL parameters for prefilling
        params = []
        if prefill_data.get("name"):
            params.append(f"name={prefill_data['name']}")
        if prefill_data.get("email"):
            params.append(f"email={prefill_data['email']}")
        if prefill_data.get("phone"):
            params.append(f"a1={prefill_data['phone']}")  # Custom question field

        if params:
            separator = "?" if "?" not in event_type_url else "&"
            return f"{event_type_url}{separator}{'&'.join(params)}"

        return event_type_url

    async def create_webhook_subscription(
        self,
        access_token: str,
        url: str,
        events: list[str],
        organization_uri: str,
        scope: str = "organization",
    ) -> dict[str, Any]:
        """
        Create a webhook subscription

        Args:
            access_token: Calendly access token
            url: Your webhook endpoint URL
            events: List of events to subscribe to (e.g., ['invitee.created', 'invitee.canceled'])
            organization_uri: Organization URI from user info
            scope: 'organization' or 'user'
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/webhook_subscriptions",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "events": events,
                    "organization": organization_uri,
                    "scope": scope,
                },
            )
            response.raise_for_status()
            return response.json()

    async def list_webhook_subscriptions(
        self, access_token: str, organization_uri: str
    ) -> dict[str, Any]:
        """List all webhook subscriptions for an organization"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/webhook_subscriptions",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"organization": organization_uri, "scope": "organization"},
            )
            response.raise_for_status()
            return response.json()

    async def delete_webhook_subscription(self, access_token: str, webhook_uuid: str) -> None:
        """Delete a webhook subscription"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/webhook_subscriptions/{webhook_uuid}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
