"""
Square OAuth and Payments Integration
Handles Square OAuth flow, invoice creation, and subscription management
"""
import logging
import os
import httpx
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from cryptography.fernet import Fernet

from ..auth import get_current_user
from ..database import get_db
from ..models import User, BusinessConfig, Contract, Client
from ..config import SECRET_KEY, FRONTEND_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/square", tags=["square"])

# Square API Configuration
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")  # sandbox or production
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

# Encryption for storing tokens
ENCRYPTION_KEY = os.getenv("SQUARE_ENCRYPTION_KEY") or Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Encrypt sensitive token data"""
    return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt sensitive token data"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


class SquareOAuthInitiate(BaseModel):
    """Request to initiate Square OAuth flow"""
    pass


class SquareOAuthCallback(BaseModel):
    """Square OAuth callback data"""
    code: str
    state: str


class SquareInvoiceCreate(BaseModel):
    """Request to create Square invoice"""
    contract_id: int
    client_id: int
    amount: float
    description: str
    due_date: Optional[str] = None


class SquareSubscriptionCreate(BaseModel):
    """Request to create Square subscription"""
    contract_id: int
    client_id: int
    amount: float
    frequency: str  # WEEKLY, EVERY_TWO_WEEKS, MONTHLY
    start_date: str


@router.get("/status")
async def get_square_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if Square is connected for the current user"""
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config:
        return {
            "connected": False,
            "merchant_id": None,
            "location_id": None,
            "auto_invoice": False,
            "auto_subscription": False
        }
    
    connected = bool(
        business_config.square_access_token and 
        business_config.square_merchant_id
    )
    
    # Check if token is expired
    if connected and business_config.square_token_expires_at:
        if datetime.utcnow() >= business_config.square_token_expires_at:
            # Token expired, try to refresh
            try:
                await refresh_square_token(business_config, db)
            except Exception as e:
                logger.error(f"Failed to refresh Square token: {e}")
                connected = False
    
    return {
        "connected": connected,
        "merchant_id": business_config.square_merchant_id if connected else None,
        "location_id": business_config.square_location_id if connected else None,
        "auto_invoice": business_config.square_auto_invoice or False,
        "auto_subscription": business_config.square_auto_subscription or False,
        "connected_at": business_config.square_connected_at.isoformat() if business_config.square_connected_at else None
    }


@router.post("/oauth/initiate")
async def initiate_square_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate Square OAuth flow"""
    if not SQUARE_APPLICATION_ID:
        raise HTTPException(status_code=500, detail="Square not configured")
    
    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state in session (you might want to use Redis for production)
    # For now, we'll validate it in the callback
    
    # Build OAuth URL
    oauth_url = (
        f"{SQUARE_BASE_URL}/oauth2/authorize"
        f"?client_id={SQUARE_APPLICATION_ID}"
        f"&scope=MERCHANT_PROFILE_READ+PAYMENTS_WRITE+INVOICES_WRITE+SUBSCRIPTIONS_WRITE+SUBSCRIPTIONS_READ"
        f"&session=false"
        f"&state={state}"
    )
    
    logger.info(f"Initiating Square OAuth for user {current_user.email}")
    
    return {
        "oauth_url": oauth_url,
        "state": state
    }


@router.post("/oauth/callback")
async def square_oauth_callback(
    callback_data: SquareOAuthCallback,
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
                    "grant_type": "authorization_code"
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Square OAuth token exchange failed: {response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
            
            token_data = response.json()
        
        # Extract token information
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_at = token_data.get("expires_at")  # ISO 8601 format
        merchant_id = token_data.get("merchant_id")
        
        if not access_token or not merchant_id:
            raise HTTPException(status_code=400, detail="Invalid token response from Square")
        
        # Get merchant's location (required for invoices)
        async with httpx.AsyncClient() as client:
            locations_response = await client.get(
                f"{SQUARE_API_URL}/locations",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if locations_response.status_code == 200:
                locations_data = locations_response.json()
                locations = locations_data.get("locations", [])
                # Use first active location
                location_id = None
                for loc in locations:
                    if loc.get("status") == "ACTIVE":
                        location_id = loc.get("id")
                        break
                
                if not location_id and locations:
                    location_id = locations[0].get("id")
            else:
                location_id = None
        
        # Encrypt tokens before storing
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        
        # Parse expiration time
        token_expires_at = None
        if expires_at:
            try:
                token_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except:
                # Default to 30 days if parsing fails
                token_expires_at = datetime.utcnow() + timedelta(days=30)
        
        # Update or create business config
        business_config = db.query(BusinessConfig).filter(
            BusinessConfig.user_id == current_user.id
        ).first()
        
        if not business_config:
            business_config = BusinessConfig(user_id=current_user.id)
            db.add(business_config)
        
        business_config.square_access_token = encrypted_access_token
        business_config.square_refresh_token = encrypted_refresh_token
        business_config.square_merchant_id = merchant_id
        business_config.square_token_expires_at = token_expires_at
        business_config.square_connected_at = datetime.utcnow()
        business_config.square_location_id = location_id
        
        db.commit()
        
        logger.info(f"Square connected successfully for user {current_user.email}, merchant: {merchant_id}")
        
        return {
            "success": True,
            "merchant_id": merchant_id,
            "location_id": location_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Square OAuth callback error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to connect Square account")


@router.post("/disconnect")
async def disconnect_square(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Square integration"""
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config:
        raise HTTPException(status_code=404, detail="Business config not found")
    
    # Revoke Square access token
    if business_config.square_access_token:
        try:
            access_token = decrypt_token(business_config.square_access_token)
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{SQUARE_BASE_URL}/oauth2/revoke",
                    json={
                        "client_id": SQUARE_APPLICATION_ID,
                        "access_token": access_token
                    },
                    headers={"Content-Type": "application/json"}
                )
        except Exception as e:
            logger.warning(f"Failed to revoke Square token: {e}")
    
    # Clear Square data
    business_config.square_access_token = None
    business_config.square_refresh_token = None
    business_config.square_merchant_id = None
    business_config.square_token_expires_at = None
    business_config.square_connected_at = None
    business_config.square_location_id = None
    business_config.square_auto_invoice = False
    business_config.square_auto_subscription = False
    
    db.commit()
    
    logger.info(f"Square disconnected for user {current_user.email}")
    
    return {"success": True}


async def refresh_square_token(business_config: BusinessConfig, db: Session):
    """Refresh Square access token"""
    if not business_config.square_refresh_token:
        raise Exception("No refresh token available")
    
    refresh_token = decrypt_token(business_config.square_refresh_token)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SQUARE_BASE_URL}/oauth2/token",
            json={
                "client_id": SQUARE_APPLICATION_ID,
                "client_secret": SQUARE_APPLICATION_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        token_data = response.json()
    
    # Update tokens
    access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")
    expires_at = token_data.get("expires_at")
    
    business_config.square_access_token = encrypt_token(access_token)
    if new_refresh_token:
        business_config.square_refresh_token = encrypt_token(new_refresh_token)
    
    if expires_at:
        try:
            business_config.square_token_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except:
            business_config.square_token_expires_at = datetime.utcnow() + timedelta(days=30)
    
    db.commit()
    logger.info(f"Square token refreshed for merchant {business_config.square_merchant_id}")


@router.post("/invoices/create")
async def create_square_invoice(
    invoice_data: SquareInvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Square invoice for a contract"""
    # Get business config
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config or not business_config.square_access_token:
        raise HTTPException(status_code=400, detail="Square not connected")
    
    # Get contract and client
    contract = db.query(Contract).filter(
        Contract.id == invoice_data.contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    client = db.query(Client).filter(
        Client.id == invoice_data.client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Decrypt access token
    access_token = decrypt_token(business_config.square_access_token)
    
    # Prepare invoice data
    invoice_payload = {
        "invoice": {
            "location_id": business_config.square_location_id,
            "order_id": None,  # We'll create an order inline
            "primary_recipient": {
                "customer_id": None,  # Square will create customer if needed
                "given_name": client.contact_name or client.business_name,
                "email_address": client.email
            },
            "payment_requests": [
                {
                    "request_type": "BALANCE",
                    "due_date": invoice_data.due_date or (datetime.utcnow() + timedelta(days=15)).strftime("%Y-%m-%d"),
                    "automatic_payment_source": "NONE"
                }
            ],
            "delivery_method": "EMAIL",
            "invoice_number": f"INV-{contract.id}",
            "title": contract.title,
            "description": invoice_data.description,
            "scheduled_at": datetime.utcnow().isoformat() + "Z"
        },
        "idempotency_key": f"invoice-{contract.id}-{int(datetime.utcnow().timestamp())}"
    }
    
    # Create order with line items
    order_payload = {
        "order": {
            "location_id": business_config.square_location_id,
            "line_items": [
                {
                    "name": contract.title,
                    "quantity": "1",
                    "base_price_money": {
                        "amount": int(invoice_data.amount * 100),  # Convert to cents
                        "currency": "USD"
                    }
                }
            ]
        },
        "idempotency_key": f"order-{contract.id}-{int(datetime.utcnow().timestamp())}"
    }
    
    try:
        # Create order first
        async with httpx.AsyncClient() as client_http:
            order_response = await client_http.post(
                f"{SQUARE_API_URL}/orders",
                json=order_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if order_response.status_code != 200:
                logger.error(f"Square order creation failed: {order_response.text}")
                raise HTTPException(status_code=400, detail="Failed to create order")
            
            order_data = order_response.json()
            order_id = order_data.get("order", {}).get("id")
            
            # Add order_id to invoice
            invoice_payload["invoice"]["order_id"] = order_id
            
            # Create invoice
            invoice_response = await client_http.post(
                f"{SQUARE_API_URL}/invoices",
                json=invoice_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if invoice_response.status_code != 200:
                logger.error(f"Square invoice creation failed: {invoice_response.text}")
                raise HTTPException(status_code=400, detail="Failed to create invoice")
            
            invoice_result = invoice_response.json()
            invoice_id = invoice_result.get("invoice", {}).get("id")
            invoice_url = invoice_result.get("invoice", {}).get("public_url")
            
            # Publish invoice (send to client)
            publish_response = await client_http.post(
                f"{SQUARE_API_URL}/invoices/{invoice_id}/publish",
                json={"version": invoice_result.get("invoice", {}).get("version")},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if publish_response.status_code != 200:
                logger.warning(f"Failed to publish invoice: {publish_response.text}")
        
        # Update contract with Square invoice info
        contract.square_invoice_id = invoice_id
        contract.square_invoice_url = invoice_url
        contract.square_payment_status = "pending"
        
        db.commit()
        
        logger.info(f"Square invoice created: {invoice_id} for contract {contract.id}")
        
        return {
            "success": True,
            "invoice_id": invoice_id,
            "invoice_url": invoice_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Square invoice creation error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create invoice")


@router.post("/subscriptions/create")
async def create_square_subscription(
    subscription_data: SquareSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Square subscription for recurring services"""
    # Get business config
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config or not business_config.square_access_token:
        raise HTTPException(status_code=400, detail="Square not connected")
    
    # Get contract and client
    contract = db.query(Contract).filter(
        Contract.id == subscription_data.contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    client = db.query(Client).filter(
        Client.id == subscription_data.client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Decrypt access token
    access_token = decrypt_token(business_config.square_access_token)
    
    # Map frequency to Square cadence
    cadence_map = {
        "weekly": "WEEKLY",
        "bi-weekly": "EVERY_TWO_WEEKS",
        "monthly": "MONTHLY"
    }
    
    cadence = cadence_map.get(subscription_data.frequency.lower(), "MONTHLY")
    
    # Create subscription plan first
    plan_payload = {
        "idempotency_key": f"plan-{contract.id}-{int(datetime.utcnow().timestamp())}",
        "subscription_plan_data": {
            "name": f"{contract.title} - {subscription_data.frequency}",
            "phases": [
                {
                    "cadence": cadence,
                    "recurring_price_money": {
                        "amount": int(subscription_data.amount * 100),
                        "currency": "USD"
                    }
                }
            ]
        }
    }
    
    try:
        async with httpx.AsyncClient() as client_http:
            # Create subscription plan
            plan_response = await client_http.post(
                f"{SQUARE_API_URL}/catalog/object",
                json=plan_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if plan_response.status_code != 200:
                logger.error(f"Square plan creation failed: {plan_response.text}")
                raise HTTPException(status_code=400, detail="Failed to create subscription plan")
            
            plan_data = plan_response.json()
            plan_id = plan_data.get("catalog_object", {}).get("id")
            
            # Create subscription
            subscription_payload = {
                "idempotency_key": f"sub-{contract.id}-{int(datetime.utcnow().timestamp())}",
                "location_id": business_config.square_location_id,
                "plan_id": plan_id,
                "customer_id": None,  # Square will create if needed
                "start_date": subscription_data.start_date
            }
            
            subscription_response = await client_http.post(
                f"{SQUARE_API_URL}/subscriptions",
                json=subscription_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if subscription_response.status_code != 200:
                logger.error(f"Square subscription creation failed: {subscription_response.text}")
                raise HTTPException(status_code=400, detail="Failed to create subscription")
            
            subscription_result = subscription_response.json()
            subscription_id = subscription_result.get("subscription", {}).get("id")
        
        # Update contract with Square subscription info
        contract.square_subscription_id = subscription_id
        contract.square_payment_status = "active"
        
        db.commit()
        
        logger.info(f"Square subscription created: {subscription_id} for contract {contract.id}")
        
        return {
            "success": True,
            "subscription_id": subscription_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Square subscription creation error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.post("/webhooks")
async def square_webhook_handler(request: Request, db: Session = Depends(get_db)):
    """Handle Square webhook events"""
    try:
        # Get webhook signature for verification
        signature = request.headers.get("x-square-signature")
        
        # Get raw body
        body = await request.body()
        
        # TODO: Verify webhook signature
        # https://developer.squareup.com/docs/webhooks/step3validate
        
        # Parse webhook data
        webhook_data = await request.json()
        
        event_type = webhook_data.get("type")
        event_id = webhook_data.get("event_id")
        merchant_id = webhook_data.get("merchant_id")
        
        # Log webhook for debugging
        from ..models_invoice import SquareWebhookLog
        webhook_log = SquareWebhookLog(
            event_type=event_type,
            event_id=event_id,
            merchant_id=merchant_id,
            payload=webhook_data,
            processed=False
        )
        db.add(webhook_log)
        db.commit()
        
        # Handle different event types
        if event_type == "invoice.payment_made":
            # Invoice paid - update contract status
            invoice_id = webhook_data.get("data", {}).get("object", {}).get("invoice", {}).get("id")
            
            if invoice_id:
                contract = db.query(Contract).filter(
                    Contract.square_invoice_id == invoice_id
                ).first()
                
                if contract:
                    contract.square_payment_status = "paid"
                    db.commit()
                    logger.info(f"Invoice {invoice_id} marked as paid for contract {contract.id}")
        
        elif event_type == "subscription.created":
            # Subscription created
            subscription_id = webhook_data.get("data", {}).get("object", {}).get("subscription", {}).get("id")
            logger.info(f"Subscription created: {subscription_id}")
        
        elif event_type == "subscription.updated":
            # Subscription updated (payment made, status changed, etc.)
            subscription_id = webhook_data.get("data", {}).get("object", {}).get("subscription", {}).get("id")
            status = webhook_data.get("data", {}).get("object", {}).get("subscription", {}).get("status")
            
            if subscription_id:
                contract = db.query(Contract).filter(
                    Contract.square_subscription_id == subscription_id
                ).first()
                
                if contract:
                    contract.square_payment_status = status.lower()
                    db.commit()
                    logger.info(f"Subscription {subscription_id} status updated to {status}")
        
        # Mark webhook as processed
        webhook_log.processed = True
        db.commit()
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Square webhook error: {e}")
        return {"success": False, "error": str(e)}


@router.put("/settings")
async def update_square_settings(
    auto_invoice: bool,
    auto_subscription: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update Square automation settings"""
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config:
        raise HTTPException(status_code=404, detail="Business config not found")
    
    business_config.square_auto_invoice = auto_invoice
    business_config.square_auto_subscription = auto_subscription
    
    db.commit()
    
    return {
        "success": True,
        "auto_invoice": auto_invoice,
        "auto_subscription": auto_subscription
    }
