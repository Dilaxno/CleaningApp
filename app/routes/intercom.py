"""
Intercom Integration Routes
Handles secure JWT generation for Intercom Messenger authentication
"""

import hashlib
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/intercom", tags=["intercom"])

# Get Intercom secret from environment
INTERCOM_SECRET_KEY = os.getenv("INTERCOM_SECRET_KEY", "")


class IntercomHashResponse(BaseModel):
    """Response model for Intercom user hash"""

    user_hash: str


@router.get("/user-hash", response_model=IntercomHashResponse)
async def get_intercom_user_hash(current_user: User = Depends(get_current_user)):
    """
    Generate a secure HMAC SHA256 hash for Intercom identity verification.

    This endpoint creates a user_hash that proves the user's identity to Intercom,
    preventing user impersonation and ensuring secure communication.

    The hash is generated using:
    - User's Firebase UID as the identifier
    - Intercom Secret Key (from environment)
    - HMAC SHA256 algorithm

    Returns:
        IntercomHashResponse: Contains the user_hash for Intercom authentication

    Raises:
        HTTPException: If Intercom secret key is not configured
    """
    if not INTERCOM_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Intercom secret key not configured")

    # Generate HMAC SHA256 hash using user's Firebase UID
    user_id = current_user.firebase_uid

    # Create HMAC hash
    user_hash = hmac.new(
        INTERCOM_SECRET_KEY.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return IntercomHashResponse(user_hash=user_hash)


@router.get("/health")
async def intercom_health_check():
    """
    Health check endpoint for Intercom integration.

    Returns:
        dict: Status of Intercom configuration
    """
    return {
        "status": "ok",
        "configured": bool(INTERCOM_SECRET_KEY),
        "message": (
            "Intercom secret key is configured"
            if INTERCOM_SECRET_KEY
            else "Intercom secret key not configured"
        ),
    }
