"""
Google Calendar Integration Routes
Handles OAuth connection and calendar syncing
"""

import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_with_plan
from ..config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from ..database import get_db
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-calendar", tags=["google-calendar"])

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - OAuth endpoint URL
GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
]


@router.get("/status")
async def get_google_calendar_status(
    current_user: User = Depends(get_current_user_with_plan), db: Session = Depends(get_db)
):
    """Get Google Calendar connection status"""
    from ..models_google_calendar import GoogleCalendarIntegration

    integration = (
        db.query(GoogleCalendarIntegration)
        .filter(GoogleCalendarIntegration.user_id == current_user.id)
        .first()
    )

    if not integration:
        return {
            "connected": False,
            "user_email": None,
            "calendar_id": None,
            "auto_sync_enabled": None,
        }

    return {
        "connected": True,
        "user_email": integration.google_user_email,
        "calendar_id": integration.google_calendar_id,
        "auto_sync_enabled": integration.auto_sync_enabled,
    }


@router.get("/connect")
async def initiate_google_calendar_oauth(current_user: User = Depends(get_current_user_with_plan)):
    """Initiate Google Calendar OAuth flow"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google Calendar not configured")

    # Build OAuth URL
    scopes = " ".join(GOOGLE_CALENDAR_SCOPES)
    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={current_user.firebase_uid}"
    )

    logger.info(f"Google Calendar OAuth initiated for user: {current_user.email}")

    return {"authorization_url": auth_url}


@router.post("/callback")
async def handle_google_calendar_callback(
    request: Request,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Handle Google Calendar OAuth callback"""
    from cryptography.fernet import Fernet

    from ..config import SECRET_KEY
    from ..models_google_calendar import GoogleCalendarIntegration

    try:
        body = await request.json()
        code = body.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="No authorization code provided")

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

            tokens = token_response.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)

            if not access_token or not refresh_token:
                raise HTTPException(status_code=400, detail="Invalid token response")

            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if user_info_response.status_code != 200:
                logger.error(f"Failed to get user info: {user_info_response.text}")
                raise HTTPException(status_code=400, detail="Failed to get user info")

            user_info = user_info_response.json()
            google_email = user_info.get("email")

            # Get primary calendar ID
            calendar_response = await client.get(
                "https://www.googleapis.com/calendar/v3/users/me/calendarList/primary",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            calendar_id = "primary"  # Default
            if calendar_response.status_code == 200:
                calendar_data = calendar_response.json()
                calendar_id = calendar_data.get("id", "primary")

        # Encrypt tokens
        cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))
        encrypted_access_token = cipher_suite.encrypt(access_token.encode()).decode()
        encrypted_refresh_token = cipher_suite.encrypt(refresh_token.encode()).decode()

        # Calculate token expiration
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Save or update integration
        integration = (
            db.query(GoogleCalendarIntegration)
            .filter(GoogleCalendarIntegration.user_id == current_user.id)
            .first()
        )

        if integration:
            integration.access_token = encrypted_access_token
            integration.refresh_token = encrypted_refresh_token
            integration.token_expires_at = token_expires_at
            integration.google_user_email = google_email
            integration.google_calendar_id = calendar_id
            integration.updated_at = datetime.utcnow()
        else:
            integration = GoogleCalendarIntegration(
                user_id=current_user.id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expires_at=token_expires_at,
                google_user_email=google_email,
                google_calendar_id=calendar_id,
                auto_sync_enabled=True,
            )
            db.add(integration)

        db.commit()

        logger.info(f"✅ Google Calendar connected for user: {current_user.email}")

        return {
            "success": True,
            "message": "Google Calendar connected successfully",
            "user_email": google_email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Google Calendar callback error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to connect Google Calendar: {str(e)}"
        ) from e


@router.post("/disconnect")
async def disconnect_google_calendar(
    current_user: User = Depends(get_current_user_with_plan), db: Session = Depends(get_db)
):
    """Disconnect Google Calendar integration"""
    from ..models_google_calendar import GoogleCalendarIntegration

    integration = (
        db.query(GoogleCalendarIntegration)
        .filter(GoogleCalendarIntegration.user_id == current_user.id)
        .first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Google Calendar not connected")

    # Revoke Google tokens
    try:
        from cryptography.fernet import Fernet

        from ..config import SECRET_KEY

        cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))
        access_token = cipher_suite.decrypt(integration.access_token.encode()).decode()

        async with httpx.AsyncClient() as client:
            await client.post(f"https://oauth2.googleapis.com/revoke?token={access_token}")
    except Exception as e:
        logger.warning(f"Failed to revoke Google tokens: {str(e)}")

    # Delete integration
    db.delete(integration)
    db.commit()

    logger.info(f"✅ Google Calendar disconnected for user: {current_user.email}")

    return {"success": True, "message": "Google Calendar disconnected"}
