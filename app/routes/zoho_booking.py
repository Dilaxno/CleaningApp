from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..models import User, ZohoBookingIntegration
from ..services.zoho_booking_service import ZohoBookingService
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zoho-booking", tags=["zoho-booking"])
zoho_service = ZohoBookingService()


class ZohoOAuthResponse(BaseModel):
    authorization_url: str
    state: str


class ZohoTokenRequest(BaseModel):
    code: str
    state: str


class ZohoConnectionStatus(BaseModel):
    connected: bool
    user_email: Optional[str] = None
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    services: Optional[List[Dict[str, Any]]] = None
    default_service: Optional[Dict[str, str]] = None


class ServiceSelection(BaseModel):
    service_id: str
    service_name: str


@router.get("/connect", response_model=ZohoOAuthResponse)
async def initiate_zoho_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate Zoho Booking OAuth flow"""
    state = secrets.token_urlsafe(32)
    
    # TODO: Store state in cache/session for validation (e.g., Redis)
    # For now, we'll trust the frontend to send it back
    
    auth_url = zoho_service.get_authorization_url(state)
    
    logger.info(f"🔗 Generated Zoho Booking auth URL for user {current_user.id}")
    
    return ZohoOAuthResponse(
        authorization_url=auth_url,
        state=state
    )


@router.post("/callback")
async def zoho_oauth_callback(
    data: ZohoTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback and store tokens"""
    try:
        logger.info(f"📥 Processing Zoho Booking callback for user {current_user.id}")
        
        # Exchange code for tokens
        token_data = await zoho_service.exchange_code_for_token(data.code)
        
        # Get user info
        user_info = await zoho_service.get_user_info(token_data["access_token"])
        
        # Get workspaces
        workspaces_data = await zoho_service.list_workspaces(token_data["access_token"])
        workspaces = workspaces_data.get("workspaces", [])
        
        # Use first workspace or create default
        workspace = workspaces[0] if workspaces else None
        
        # Calculate token expiry
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        
        # Check if integration exists
        integration = db.query(ZohoBookingIntegration).filter(
            ZohoBookingIntegration.user_id == current_user.id
        ).first()
        
        if integration:
            # Update existing
            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data.get("refresh_token", "")
            integration.token_expires_at = expires_at
            integration.zoho_user_id = user_info.get("user_id", "")
            integration.zoho_user_email = user_info.get("email", "")
            integration.zoho_org_id = user_info.get("org_id", "")
            if workspace:
                integration.workspace_id = workspace.get("workspace_id")
                integration.workspace_name = workspace.get("workspace_name")
            logger.info(f"✅ Updated Zoho Booking integration for user {current_user.id}")
        else:
            # Create new
            integration = ZohoBookingIntegration(
                user_id=current_user.id,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                token_expires_at=expires_at,
                zoho_user_id=user_info.get("user_id", ""),
                zoho_user_email=user_info.get("email", ""),
                zoho_org_id=user_info.get("org_id", ""),
                workspace_id=workspace.get("workspace_id") if workspace else None,
                workspace_name=workspace.get("workspace_name") if workspace else None
            )
            db.add(integration)
            logger.info(f"✅ Created new Zoho Booking integration for user {current_user.id}")
        
        db.commit()
        
        return {
            "message": "Zoho Booking connected successfully",
            "email": user_info.get("email", ""),
            "workspace": workspace.get("workspace_name") if workspace else None
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to connect Zoho Booking for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect Zoho Booking: {str(e)}")


async def _ensure_fresh_token(integration: ZohoBookingIntegration, db: Session) -> str:
    """Ensure access token is fresh, refresh if needed"""
    if datetime.utcnow() >= integration.token_expires_at - timedelta(minutes=5):
        logger.info(f"🔄 Refreshing Zoho Booking token for user {integration.user_id}")
        try:
            token_data = await zoho_service.refresh_access_token(integration.refresh_token)
            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data.get("refresh_token", integration.refresh_token)
            integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
            db.commit()
            logger.info(f"✅ Token refreshed for user {integration.user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to refresh token for user {integration.user_id}: {str(e)}")
            raise HTTPException(status_code=401, detail="Zoho Booking token expired. Please reconnect.")
    
    return integration.access_token


@router.get("/status", response_model=ZohoConnectionStatus)
async def get_zoho_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Zoho Booking connection status and services"""
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        return ZohoConnectionStatus(connected=False)
    
    try:
        # Ensure token is fresh
        access_token = await _ensure_fresh_token(integration, db)
        
        services = []
        if integration.workspace_id:
            # Get services
            services_data = await zoho_service.list_services(
                access_token,
                integration.workspace_id
            )
            services = services_data.get("services", [])
        
        default_service = None
        if integration.default_service_id:
            default_service = {
                "service_id": integration.default_service_id,
                "service_name": integration.default_service_name
            }
        
        return ZohoConnectionStatus(
            connected=True,
            user_email=integration.zoho_user_email,
            workspace_id=integration.workspace_id,
            workspace_name=integration.workspace_name,
            services=services,
            default_service=default_service
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Zoho Booking status: {str(e)}")
        return ZohoConnectionStatus(connected=False)


@router.post("/disconnect")
async def disconnect_zoho(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Zoho Booking integration"""
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="No Zoho Booking integration found")
    
    db.delete(integration)
    db.commit()
    
    logger.info(f"🔌 Disconnected Zoho Booking for user {current_user.id}")
    
    return {"message": "Zoho Booking disconnected successfully"}


@router.post("/service")
async def set_default_service(
    data: ServiceSelection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set default service for cleaning appointments"""
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Zoho Booking not connected")
    
    integration.default_service_id = data.service_id
    integration.default_service_name = data.service_name
    db.commit()
    
    logger.info(f"🧹 Set default service for user {current_user.id}: {data.service_name}")
    
    return {"message": "Default service updated"}


@router.post("/create-service")
async def create_cleaning_service(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a default cleaning service in Zoho Booking"""
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration or not integration.workspace_id:
        raise HTTPException(status_code=404, detail="Zoho Booking not properly configured")
    
    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)
    
    # Create default cleaning service
    service_data = {
        "service_name": "House Cleaning Service",
        "service_description": "Professional house cleaning service",
        "duration": 120,  # 2 hours default
        "price": 100,  # Default price, can be customized
        "currency": "USD",
        "booking_type": "appointment",
        "status": "active"
    }
    
    try:
        service_response = await zoho_service.create_service(
            access_token,
            integration.workspace_id,
            service_data
        )
        
        # Set as default service
        service_id = service_response.get("service_id")
        if service_id:
            integration.default_service_id = service_id
            integration.default_service_name = service_data["service_name"]
            db.commit()
        
        logger.info(f"🧹 Created default cleaning service for user {current_user.id}")
        
        return {
            "message": "Cleaning service created successfully",
            "service": service_response
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to create service: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to create service: {str(e)}")


@router.get("/booking-link/{client_id}")
async def get_client_booking_link(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a Zoho Booking link for a specific client with prefilled data"""
    from ..models import Client
    
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration or not integration.default_service_id or not integration.workspace_id:
        raise HTTPException(
            status_code=404, 
            detail="Zoho Booking not configured. Please connect Zoho Booking and set up a service."
        )
    
    # Get client info
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Generate prefilled booking link
    prefill_data = {
        "name": client.contact_name or client.business_name,
        "email": client.email,
        "phone": client.phone
    }
    
    booking_link = zoho_service.generate_public_booking_link(
        integration.workspace_id,
        integration.default_service_id,
        prefill_data
    )
    
    return {
        "booking_link": booking_link,
        "service_name": integration.default_service_name,
        "client_name": client.business_name,
        "workspace_name": integration.workspace_name
    }


@router.get("/bookings")
async def get_upcoming_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None)
):
    """Get upcoming bookings from Zoho Booking"""
    integration = db.query(ZohoBookingIntegration).filter(
        ZohoBookingIntegration.user_id == current_user.id
    ).first()
    
    if not integration or not integration.workspace_id:
        raise HTTPException(status_code=404, detail="Zoho Booking not connected")
    
    # Ensure token is fresh
    access_token = await _ensure_fresh_token(integration, db)
    
    # Parse dates
    from_datetime = None
    to_datetime = None
    if from_date:
        from_datetime = datetime.fromisoformat(from_date)
    if to_date:
        to_datetime = datetime.fromisoformat(to_date)
    
    # Get bookings
    bookings_data = await zoho_service.get_bookings(
        access_token,
        integration.workspace_id,
        from_date=from_datetime,
        to_date=to_datetime
    )
    
    return bookings_data