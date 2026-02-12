"""
Square OAuth and Payments Integration
Clean implementation using Square OAuth 2.0 (latest version)
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

# Square API URLs (OAuth 2.0 endpoints)
# Note: Sandbox and Production use DIFFERENT OAuth URLs
if SQUARE_ENVIRONMENT == "production":
    SQUARE_OAUTH_URL = "https://connect.squareup.com"
    SQUARE_API_URL = "https://connect.squareup.com/v2"
else:
    SQUARE_OAUTH_URL = "https://connect.squareupsandbox.com"
    SQUARE_API_URL = "https://connect.squareupsandbox.com/v2"

# Encryption for tokens
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b'='))


# Pydantic Models
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
@router.get("/config/test")
async def test_config():
    """Test endpoint to verify Square configuration (for debugging)"""
    return {
        "environment": SQUARE_ENVIRONMENT,
        "oauth_url": SQUARE_OAUTH_URL,
        "api_url": SQUARE_API_URL,
        "app_id_configured": bool(SQUARE_APPLICATION_ID),
        "app_secret_configured": bool(SQUARE_APPLICATION_SECRET),
        "redirect_uri": SQUARE_REDIRECT_URI,
        "frontend_url": FRONTEND_URL
    }


@router.post("/oauth/initiate")
async def initiate_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate Square OAuth 2.0 flow
    Returns authorization URL following Square's latest OAuth 2.0 specification
    """
    if not SQUARE_APPLICATION_ID:
        raise HTTPException(status_code=500, detail="Square not configured")
    
    # Generate CSRF state token for security
    state = secrets.token_urlsafe(32)
    
    # Build OAuth 2.0 authorization URL with proper encoding
    # Square expects spaces in scope to be encoded as + signs
    scope = "MERCHANT_PROFILE_READ PAYMENTS_WRITE ORDERS_WRITE INVOICES_WRITE CUSTOMERS_READ CUSTOMERS_WRITE SUBSCRIPTIONS_WRITE SUBSCRIPTIONS_READ"
    scope_encoded = scope.replace(" ", "+")
    
    # Build the full OAuth URL
    # Note: Different OAuth URLs for sandbox vs production
    oauth_url = (
        f"{SQUARE_OAUTH_URL}/oauth2/authorize"
        f"?client_id={SQUARE_APPLICATION_ID}"
        f"&response_type=code"
        f"&scope={scope_encoded}"
        f"&state={state}"
        f"&redirect_uri={quote(SQUARE_REDIRECT_URI, safe='')}"
    )
    
    logger.info(f"Square OAuth 2.0 initiated for user: {current_user.email}")
    logger.info(f"Environment: {SQUARE_ENVIRONMENT}")
    logger.info(f"OAuth URL: {SQUARE_OAUTH_URL}")
    logger.info(f"Redirect URI: {SQUARE_REDIRECT_URI}")
    logger.info(f"Full OAuth URL: {oauth_url}")
    
    return {
        "oauth_url": oauth_url,
        "state": state
    }


@router.get("/callback-handler")
async def oauth_callback_handler(
    code: str,
    state: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete Square OAuth 2.0 flow
    Called by frontend after Square redirects with authorization code
    Exchanges code for tokens and stores them
    """
    if not SQUARE_APPLICATION_ID or not SQUARE_APPLICATION_SECRET:
        raise HTTPException(status_code=500, detail="Square not configured")
    
    try:
        logger.info(f"Square OAuth callback handler for user: {current_user.email}")
        logger.info(f"Authorization code: {code[:20]}...")
        
        # Exchange authorization code for access token
        token_payload = {
            "client_id": SQUARE_APPLICATION_ID,
            "client_secret": SQUARE_APPLICATION_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": SQUARE_REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_OAUTH_URL}/oauth2/token",
                json=token_payload,
                headers={
                    "Content-Type": "application/json",
                    "Square-Version": "2024-12-18"
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Square token exchange failed: {error_detail}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to exchange authorization code: {error_detail}"
                )
            
            token_data = response.json()
        
        # Extract tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        merchant_id = token_data.get("merchant_id")
        expires_at_str = token_data.get("expires_at")
        
        if not access_token or not merchant_id:
            raise HTTPException(status_code=400, detail="Invalid token response from Square")
        
        # Parse expiration
        expires_at = None
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            except Exception as e:
                logger.warning(f"Failed to parse expires_at: {e}")
        
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
        
    except HTTPException:
        raise
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
                f"{SQUARE_OAUTH_URL}/oauth2/revoke",
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


@router.get("/invoices")
async def get_paid_invoices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """Get all Square invoices with optional filtering"""
    from ..models import Contract
    from sqlalchemy import and_, or_
    
    # Base query for contracts with Square invoices
    query = db.query(Contract).filter(
        Contract.user_id == current_user.id,
        Contract.square_invoice_id.isnot(None)
    )
    
    # Filter by payment status
    if status:
        query = query.filter(Contract.square_payment_status == status)
    else:
        # Default to showing paid invoices
        query = query.filter(Contract.square_payment_status == "paid")
    
    # Filter by date range
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(Contract.square_invoice_created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(Contract.square_invoice_created_at <= end_dt)
        except ValueError:
            pass
    
    # Get contracts ordered by invoice creation date (newest first)
    contracts = query.order_by(Contract.square_invoice_created_at.desc()).all()
    
    # Format response
    invoices = []
    for contract in contracts:
        # Get client name from the relationship
        client_name = None
        if contract.client:
            client_name = contract.client.contact_name or contract.client.business_name
        
        invoices.append({
            "id": contract.id,
            "invoice_id": contract.square_invoice_id,
            "invoice_url": contract.square_invoice_url,
            "client_id": contract.client_id,
            "client_name": client_name,
            "amount": float(contract.total_value) if contract.total_value else 0.0,
            "payment_status": contract.square_payment_status,
            "created_at": contract.square_invoice_created_at.isoformat() if contract.square_invoice_created_at else None,
            "paid_at": contract.square_payment_received_at.isoformat() if contract.square_payment_received_at else None,
            "contract_title": contract.title,
            "frequency": contract.frequency
        })
    
    return {
        "invoices": invoices,
        "total": len(invoices)
    }
