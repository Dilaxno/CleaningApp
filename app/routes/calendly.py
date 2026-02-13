import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import CalendlyIntegration, User
from ..services.calendly_service import CalendlyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendly", tags=["calendly"])
calendly_service = CalendlyService()


class CalendlyOAuthResponse(BaseModel):
    authorization_url: str
    state: str


class CalendlyTokenRequest(BaseModel):
    code: str
    state: str


class CalendlyConnectionStatus(BaseModel):
    connected: bool
    user_email: Optional[str] = None
    event_types: Optional[list[dict[str, Any]]] = None
    default_event_type: Optional[dict[str, str]] = None


class EventTypeUpdate(BaseModel):
    event_type_uri: str
    event_type_name: str
    event_type_url: str


@router.get("/connect", response_model=CalendlyOAuthResponse)
async def initiate_calendly_connection(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Initiate Calendly OAuth flow"""
    state = secrets.token_urlsafe(32)

    # TODO: Store state in cache/session for validation (e.g., Redis)
    # For now, we'll trust the frontend to send it back

    auth_url = calendly_service.get_authorization_url(state)
    return CalendlyOAuthResponse(authorization_url=auth_url, state=state)


@router.post("/callback")
async def calendly_oauth_callback(
    data: CalendlyTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle OAuth callback and store tokens"""
    try:
        # Exchange code for tokens
        token_data = await calendly_service.exchange_code_for_token(data.code)

        # Get user info
        user_info = await calendly_service.get_user_info(token_data["access_token"])

        # Calculate token expiry
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 7200))

        # Check if integration exists
        integration = (
            db.query(CalendlyIntegration)
            .filter(CalendlyIntegration.user_id == current_user.id)
            .first()
        )

        if integration:
            # Update existing
            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data["refresh_token"]
            integration.token_expires_at = expires_at
            integration.calendly_user_uri = user_info["resource"]["uri"]
            integration.calendly_user_email = user_info["resource"]["email"]
            integration.calendly_organization_uri = user_info["resource"].get(
                "current_organization"
            )
        else:
            # Create new
            integration = CalendlyIntegration(
                user_id=current_user.id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                token_expires_at=expires_at,
                calendly_user_uri=user_info["resource"]["uri"],
                calendly_user_email=user_info["resource"]["email"],
                calendly_organization_uri=user_info["resource"].get("current_organization"),
            )
            db.add(integration)
        db.commit()
        db.refresh(integration)

        # Auto-select first event type as default
        try:
            event_types_data = await calendly_service.list_event_types(
                token_data["access_token"], user_info["resource"]["uri"]
            )

            event_types = event_types_data.get("collection", [])
            if event_types:
                # Set first event type as default
                first_event = event_types[0]
                integration.default_event_type_uri = first_event.get("uri")
                integration.default_event_type_name = first_event.get("name")
                integration.default_event_type_url = first_event.get("scheduling_url")
                db.commit()
        except Exception as event_err:
            logger.warning(f"⚠️ Failed to auto-select event type: {event_err}")
            # Don't fail the connection if event type selection fails

        return {
            "message": "Calendly connected successfully",
            "email": user_info["resource"]["email"],
            "default_event_set": integration.default_event_type_uri is not None,
        }

    except Exception as e:
        logger.error(f"❌ Failed to connect Calendly for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect Calendly: {str(e)}") from e


async def _ensure_fresh_token(integration: CalendlyIntegration, db: Session) -> str:
    """Ensure access token is fresh, refresh if needed"""
    if datetime.utcnow() >= integration.token_expires_at - timedelta(minutes=5):
        logger.info(f"🔄 Refreshing Calendly token for user {integration.user_id}")
        try:
            token_data = await calendly_service.refresh_access_token(integration.refresh_token)
            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data.get("refresh_token", integration.refresh_token)
            integration.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 7200)
            )
            db.commit()
        except Exception as e:
            logger.error(f"❌ Failed to refresh token for user {integration.user_id}: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Calendly token expired. Please reconnect."
            ) from e

    return integration.access_token


@router.get("/status", response_model=CalendlyConnectionStatus)
async def get_calendly_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get Calendly connection status and event types"""
    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration:
        return CalendlyConnectionStatus(connected=False)

    try:
        # Ensure token is fresh
        access_token = await _ensure_fresh_token(integration, db)

        # Get event types
        event_types_data = await calendly_service.list_event_types(
            access_token, integration.calendly_user_uri
        )

        event_types = [
            {
                "uri": et["uri"],
                "name": et["name"],
                "duration": et["duration"],
                "booking_url": et["scheduling_url"],
            }
            for et in event_types_data.get("collection", [])
        ]

        default_event = None
        if integration.default_event_type_uri:
            default_event = {
                "uri": integration.default_event_type_uri,
                "name": integration.default_event_type_name,
                "url": integration.default_event_type_url,
            }

        return CalendlyConnectionStatus(
            connected=True,
            user_email=integration.calendly_user_email,
            event_types=event_types,
            default_event_type=default_event,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Calendly status: {str(e)}")
        return CalendlyConnectionStatus(connected=False)


@router.post("/disconnect")
async def disconnect_calendly(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Disconnect Calendly integration"""
    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="No Calendly integration found") from e

    # TODO: Optionally delete webhook subscriptions before disconnecting

    db.delete(integration)
    db.commit()

    logger.info(f"🔌 Disconnected Calendly for user {current_user.id}")

    return {"message": "Calendly disconnected successfully"}


@router.put("/event-type")
async def set_default_event_type(
    data: EventTypeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set default event type for scheduling"""
    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Calendly not connected")

    integration.default_event_type_uri = data.event_type_uri
    integration.default_event_type_name = data.event_type_name
    integration.default_event_type_url = data.event_type_url
    db.commit()

    logger.info(f"📅 Set default event type for user {current_user.id}: {data.event_type_name}")

    return {"message": "Default event type updated"}


@router.get("/events")
async def get_upcoming_events(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get upcoming scheduled events from Calendly with invitee details"""
    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Calendly not connected")

    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)

    # Get events from now onwards
    events_data = await calendly_service.get_scheduled_events(
        access_token, integration.calendly_user_uri, min_start_time=datetime.utcnow()
    )

    # Enrich events with invitee information
    enriched_events = []
    for event in events_data.get("collection", []):
        # Extract event UUID from URI
        event_uuid = event.get("uri", "").split("/")[-1]

        try:
            # Get invitees for this event
            invitees_data = await calendly_service.get_event_invitees(access_token, event_uuid)
            invitees = invitees_data.get("collection", [])

            if invitees:
                # Add first invitee info to event
                first_invitee = invitees[0]
                event["invitee"] = {
                    "name": first_invitee.get("name"),
                    "email": first_invitee.get("email"),
                }
        except Exception as e:
            logger.warning(f"Failed to get invitees for event {event_uuid}: {e}")

        enriched_events.append(event)

    return {"collection": enriched_events}


@router.get("/scheduling-link/{client_id}")
async def get_client_scheduling_link(
    client_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Generate a Calendly scheduling link for a specific client with prefilled data"""
    from ..models import Client

    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration or not integration.default_event_type_url:
        raise HTTPException(
            status_code=404,
            detail="Calendly not configured. Please connect Calendly and set a default event type.",
        ) from e

    # Get client info
    client = (
        db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    )

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Generate prefilled scheduling link
    prefill_data = {
        "name": client.contact_name or client.business_name,
        "email": client.email,
        "phone": client.phone,
    }

    scheduling_link = calendly_service.generate_scheduling_link(
        integration.default_event_type_url, prefill_data
    )

    return {
        "scheduling_link": scheduling_link,
        "event_type_name": integration.default_event_type_name,
        "client_name": client.business_name,
    }


@router.delete("/events/{event_uuid}")
async def cancel_calendly_event(
    event_uuid: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Cancel a Calendly event (consultation)"""
    integration = (
        db.query(CalendlyIntegration).filter(CalendlyIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Calendly not connected")

    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)

    try:
        # First, try to get event details to verify ownership and status
        try:
            event_details = await calendly_service.get_event_details(access_token, event_uuid)
            event_data = event_details.get("resource", {})

            # Check if event is already cancelled
            if event_data.get("status") == "canceled":
                return {"message": "Consultation was already cancelled"}

            # Log event owner information for debugging
            event_type_uri = event_data.get("event_type")
            logger.info(f"🔍 Event {event_uuid} belongs to event type: {event_type_uri}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found. The consultation may have already been cancelled or the event ID is incorrect.",
                )
            elif e.response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied. You may not have access to this event.",
                )
            # For other errors, continue with cancellation attempt
            logger.warning(f"⚠️ Could not verify event details, proceeding with cancellation: {e}")

        # Cancel the event via Calendly API
        await calendly_service.cancel_event(
            access_token, event_uuid, reason="Cancelled by provider"
        )
        return {"message": "Consultation cancelled successfully"}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.error(
                f"❌ 403 Forbidden cancelling event {event_uuid} for user {current_user.id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Permission denied. You may not be the owner of this event, or it may already be cancelled. Only the event owner can cancel events through the API.",
            )
        elif e.response.status_code == 404:
            logger.error(
                f"❌ 404 Not Found cancelling event {event_uuid} for user {current_user.id}"
            )
            raise HTTPException(
                status_code=404,
                detail="Event not found. The consultation may have already been cancelled or the event ID is incorrect.",
            )
        elif e.response.status_code == 401:
            logger.error(
                f"❌ 401 Unauthorized cancelling event {event_uuid} for user {current_user.id}"
            )
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Please disconnect and reconnect your Calendly account.",
            )
        else:
            logger.error(
                f"❌ HTTP {e.response.status_code} cancelling event {event_uuid} for user {current_user.id}: {str(e)}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to cancel consultation: {str(e)}",
            )
    except Exception as e:
        logger.error(
            f"❌ Unexpected error cancelling event {event_uuid} for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel consultation: {str(e)}"
        ) from e
