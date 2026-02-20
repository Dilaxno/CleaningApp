"""
Intercom Integration Routes
Handles secure JWT generation for Intercom Messenger authentication
"""

import os
import time

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel

from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/intercom", tags=["intercom"])

# Get Intercom secret from environment
INTERCOM_SECRET_KEY = os.getenv("INTERCOM_SECRET_KEY", "")


class IntercomJWTResponse(BaseModel):
    """Response model for Intercom JWT token"""

    jwt_token: str
    user_id: str
    email: str
    name: str


@router.get("/jwt", response_model=IntercomJWTResponse)
async def get_intercom_jwt(current_user: User = Depends(get_current_user)):
    """
    Generate a secure JWT token for Intercom identity verification.

    This endpoint creates a JWT that proves the user's identity to Intercom,
    preventing user impersonation and ensuring secure communication.

    The JWT includes:
    - User ID (Firebase UID)
    - User email
    - User name
    - Issued at timestamp
    - Expiration (1 hour)

    Returns:
        IntercomJWTResponse: Contains the JWT token and user details

    Raises:
        HTTPException: If Intercom secret key is not configured
    """
    if not INTERCOM_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Intercom secret key not configured")

    # Prepare JWT payload
    now = int(time.time())
    payload = {
        "user_id": current_user.firebase_uid,
        "email": current_user.email,
        "name": current_user.business_name or current_user.email.split("@")[0],
        "iat": now,  # Issued at
        "exp": now + 3600,  # Expires in 1 hour
    }

    # Generate JWT token
    try:
        token = jwt.encode(payload, INTERCOM_SECRET_KEY, algorithm="HS256")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate JWT: {str(e)}")

    return IntercomJWTResponse(
        jwt_token=token,
        user_id=current_user.firebase_uid,
        email=current_user.email,
        name=current_user.business_name or current_user.email.split("@")[0],
    )


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
