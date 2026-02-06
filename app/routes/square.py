"""
Square OAuth and Payments Integration
Clean implementation of Square OAuth flow and payment processing
"""
import logging
import os
import httpx
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from cryptography.fernet import Fernet

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..models_square import SquareIntegration
from ..config import SECRET_KEY, FRONTEND_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/square", tags=["square"])

# Square Configuration
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
SQUARE_APPLICATION_ID = os.getenv("SQUARE_APPLICATION_ID")
SQUARE_APPLICATION_SECRET = os.getenv("SQUARE_APPLICATION_SECRET")
SQUARE_REDIRECT_URI = os.getenv("SQUARE_REDIRECT_URI", f"{FRONTEND_URL}/auth/square/callback")

# Square API URLs
if SQUARE_ENVIRONMENT == "production":
    SQUARE_BASE_URL = "https://connect.squareup.com"
    SQUARE_API_URL = "https://connect.squareup.com/v2"
else:
    SQUARE_BASE_URL = "https://connect.squareupsandbox.com"
    SQUARE_API_URL = "https://connect.squareupsandbox.com/v2"

# Encryption for tokens
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b'='))


# Pydantic Models
class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class SquareStatusResponse(BaseModel):
    connected: bool
    merchant_id: Optional[str] = None


# Helper Functions
def encrypt_token(token: str) -> str:
    """Encrypt a token for storage"""
    return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# Routes
@router.post("/oauth/initiate")
async def initiate_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate Square OAuth flow"""
    if not SQUARE_APPLICATION_ID:
        raise HTTPException(status_code=500, detail="Square not configured")
    
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    
    # Build OAuth URL with proper encoding
    redirect_uri_encoded = quote(SQUARE_REDIRECT_URI, safe='')
    oauth_url = (
        f"{SQUARE_BASE_URL}/oauth2/authorize"
        f"?client_id={SQUARE_APPLICATION_ID}"
        f"&scope=MERCHANT_PROFILE_READ+PAYMENTS_WRITE+INVOICES_WRITE+SUBSCRIPTIONS_WRITE+SUBSCRIPTIONS_READ"
        f"&session=false"
        f"&state={state}"
        f"&redirect_uri={redirect_uri_encoded}"
    )
    
    logger.info(f"Square OAuth initiated for user: {current_user.email}")
    logger.info(f"Redirect URI: {SQUARE_REDIRECT_URI}")
    logger.info(f"Environment: {SQUARE_ENVIRONMENT}")
    
    return {
        "oauth_url": oauth_url,
        "state": state
    }


@router.post("/oauth/callback")
async def oauth_callback(
    callback_data: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle Square OAuth callback"""
    if not SQUARE_APPLICATION_ID or not SQUARE_APPLICATION_SECRET:
        raise HTTPException(status_code=500, detail="Square not configured")
    
    try:
        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_BASE_URL}/oauth2/token",
                json={
                    "client_id": SQUARE_APPLICATION_ID,
                    "client_secret": SQUARE_APPLICATION_SECRET,
                    "code": callback_data.code,
                    "grant_type": "authorization_code",
                    "redirect_uri": SQUARE_REDIRECT_URI
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Square token exchange failed: {response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
            
            token_data = response.json()
        
        # Extract tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        merchant_id = token_data.get("merchant_id")
        expires_at = None
        
        if token_data.get("expires_at"):
            expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
        
        # Encrypt tokens
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        
        # Store or update integration
        integration = db.query(SquareIntegration).filter(
            SquareIntegration.user_id == current_user.firebase_uid
        ).first()
        
        if integration:
            integration.merchant_id = merchant_id
            integration.access_token = encrypted_access_token
            integration.refresh_token = encrypted_refresh_token
            integration.token_expires_at = expires_at
            integration.is_active = True
            integration.updated_at = datetime.utcnow()
        else:
            integration = SquareIntegration(
                user_id=current_user.firebase_uid,
                merchant_id=merchant_id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expires_at=expires_at,
                is_active=True
            )
            db.add(integration)
        
        db.commit()
        
        logger.info(f"Square connected successfully for user: {current_user.email}")
        
        return {
            "success": True,
            "merchant_id": merchant_id
        }
        
    except Exception as e:
        logger.error(f"Square OAuth callback error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to complete Square connection")


@router.get("/status")
async def get_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user has Square connected"""
    integration = db.query(SquareIntegration).filter(
        SquareIntegration.user_id == current_user.firebase_uid,
        SquareIntegration.is_active == True
    ).first()
    
    if integration:
        return SquareStatusResponse(
            connected=True,
            merchant_id=integration.merchant_id
        )
    
    return SquareStatusResponse(connected=False)


@router.post("/disconnect")
async def disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Square integration"""
    integration = db.query(SquareIntegration).filter(
        SquareIntegration.user_id == current_user.firebase_uid
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Square not connected")
    
    try:
        # Revoke token with Square
        access_token = decrypt_token(integration.access_token)
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SQUARE_BASE_URL}/oauth2/revoke",
                json={
                    "client_id": SQUARE_APPLICATION_ID,
                    "access_token": access_token
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}"
                }
            )
        
        # Mark as inactive
        integration.is_active = False
        integration.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Square disconnected for user: {current_user.email}")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Square disconnect error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to disconnect Square")
