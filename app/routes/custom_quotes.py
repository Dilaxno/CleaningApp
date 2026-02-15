"""
Custom Quote Requests
Handles client custom quote requests and provider responses
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import FRONTEND_URL
from ..database import get_db
from ..email_service import send_email
from ..models import BusinessConfig, Client, CustomQuoteRequest, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/custom-quote-requests", tags=["Custom Quotes"])


# Pydantic Models
class CustomQuoteRequestCreate(BaseModel):
    client_notes: str
    video_r2_key: Optional[str] = None
    video_filename: Optional[str] = None
    video_size_bytes: Optional[int] = None
    video_duration_seconds: Optional[float] = None
    video_mime_type: Optional[str] = None


class LineItem(BaseModel):
    name: str
    quantity: float
    unit_price: float


class CustomQuoteSubmit(BaseModel):
    amount: float
    description: str
    line_items: Optional[list[LineItem]] = None
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class CustomQuoteResponse(BaseModel):
    id: int
    public_id: str
    status: str
    client_notes: Optional[str]
    custom_quote_amount: Optional[float]
    custom_quote_description: Optional[str]
    custom_quote_line_items: Optional[list[dict]]
    custom_quote_notes: Optional[str]
    quoted_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime


# Client Endpoints (Public)
@router.post("/client/{client_id}/request")
async def submit_custom_quote_request(
    client_id: int,
    request_data: CustomQuoteRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Client submits a custom quote request
    Public endpoint - no authentication required
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get provider
        provider = db.query(User).filter(User.id == client.user_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Create custom quote request
        quote_request = CustomQuoteRequest(
            user_id=client.user_id,
            client_id=client_id,
            client_notes=request_data.client_notes,
            video_r2_key=request_data.video_r2_key or "",
            video_filename=request_data.video_filename or "",
            video_size_bytes=request_data.video_size_bytes or 0,
            video_duration_seconds=request_data.video_duration_seconds,
            video_mime_type=request_data.video_mime_type or "video/mp4",
            status="pending",
            client_ip=request.client.host if request.client else None,
            client_user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(days=30),  # Default 30 days
        )

        db.add(quote_request)
        db.commit()
        db.refresh(quote_request)

        logger.info(f"✅ Custom quote request created: {quote_request.id} for client {client_id}")

        # Send notification email to provider
        await send_custom_quote_request_notification(
            provider=provider, client=client, quote_request=quote_request, db=db
        )

        return {
            "success": True,
            "request_id": quote_request.id,
            "public_id": quote_request.public_id,
            "status": quote_request.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create custom quote request: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create custom quote request") from e


@router.get("/public/{public_id}")
async def get_custom_quote_by_public_id(public_id: str, db: Session = Depends(get_db)):
    """
    Get custom quote request by public ID
    Public endpoint for client to view their quote
    """
    try:
        quote_request = (
            db.query(CustomQuoteRequest).filter(CustomQuoteRequest.public_id == public_id).first()
        )

        if not quote_request:
            raise HTTPException(status_code=404, detail="Quote request not found")

        # Get client info
        client = db.query(Client).filter(Client.id == quote_request.client_id).first()

        # Get business config for branding
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == quote_request.user_id).first()
        )

        return {
            "id": quote_request.id,
            "public_id": quote_request.public_id,
            "status": quote_request.status,
            "client_notes": quote_request.client_notes,
            "custom_quote_amount": quote_request.custom_quote_amount,
            "custom_quote_description": quote_request.custom_quote_description,
            "custom_quote_line_items": quote_request.custom_quote_line_items,
            "custom_quote_notes": quote_request.custom_quote_notes,
            "quoted_at": quote_request.quoted_at,
            "expires_at": quote_request.expires_at,
            "created_at": quote_request.created_at,
            "client_name": client.contact_name or client.business_name if client else None,
            "business_name": (
                business_config.business_name if business_config else "Service Provider"
            ),
            "business_logo": business_config.logo_url if business_config else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get custom quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quote") from e


@router.post("/public/{public_id}/approve")
async def approve_custom_quote(public_id: str, db: Session = Depends(get_db)):
    """
    Client approves the custom quote
    Public endpoint - redirects to scheduling
    """
    try:
        quote_request = (
            db.query(CustomQuoteRequest).filter(CustomQuoteRequest.public_id == public_id).first()
        )

        if not quote_request:
            raise HTTPException(status_code=404, detail="Quote request not found")

        if quote_request.status != "quoted":
            raise HTTPException(status_code=400, detail="Quote not available for approval")

        # Check if expired
        if quote_request.expires_at and quote_request.expires_at < datetime.utcnow():
            quote_request.status = "expired"
            db.commit()
            raise HTTPException(status_code=400, detail="Quote has expired")

        # Update status
        quote_request.status = "approved"
        quote_request.client_response = "approved"
        quote_request.responded_at = datetime.utcnow()

        db.commit()
        db.refresh(quote_request)

        logger.info(f"✅ Custom quote approved: {quote_request.id}")

        return {
            "success": True,
            "status": "approved",
            "client_id": quote_request.client_id,
            "redirect_url": f"/client/{quote_request.client_id}/schedule",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to approve quote: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to approve quote") from e


# Provider Endpoints (Authenticated)
@router.get("")
async def list_custom_quote_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    """
    List all custom quote requests for the provider
    """
    try:
        query = db.query(CustomQuoteRequest).filter(CustomQuoteRequest.user_id == current_user.id)

        if status:
            query = query.filter(CustomQuoteRequest.status == status)

        requests = query.order_by(CustomQuoteRequest.created_at.desc()).all()

        # Enrich with client info
        result = []
        for req in requests:
            client = db.query(Client).filter(Client.id == req.client_id).first()
            result.append(
                {
                    "id": req.id,
                    "public_id": req.public_id,
                    "status": req.status,
                    "client_id": req.client_id,
                    "client_name": (
                        client.contact_name or client.business_name if client else "Unknown"
                    ),
                    "client_email": client.email if client else None,
                    "client_phone": client.phone if client else None,
                    "client_notes": req.client_notes,
                    "has_video": bool(req.video_r2_key),
                    "custom_quote_amount": req.custom_quote_amount,
                    "quoted_at": req.quoted_at,
                    "expires_at": req.expires_at,
                    "created_at": req.created_at,
                }
            )

        return {"requests": result, "total": len(result)}

    except Exception as e:
        logger.error(f"❌ Failed to list custom quote requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve requests") from e


@router.get("/{request_id}")
async def get_custom_quote_request(
    request_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get detailed custom quote request
    """
    try:
        quote_request = (
            db.query(CustomQuoteRequest)
            .filter(
                CustomQuoteRequest.id == request_id, CustomQuoteRequest.user_id == current_user.id
            )
            .first()
        )

        if not quote_request:
            raise HTTPException(status_code=404, detail="Quote request not found")

        # Mark as viewed
        if not quote_request.provider_viewed_at:
            quote_request.provider_viewed_at = datetime.utcnow()
            db.commit()

        # Get client details
        client = db.query(Client).filter(Client.id == quote_request.client_id).first()

        return {
            "id": quote_request.id,
            "public_id": quote_request.public_id,
            "status": quote_request.status,
            "client": {
                "id": client.id,
                "name": client.contact_name or client.business_name,
                "email": client.email,
                "phone": client.phone,
                "property_type": client.property_type,
                "property_size": client.property_size,
                "frequency": client.frequency,
                "form_data": client.form_data,
            },
            "client_notes": quote_request.client_notes,
            "video": (
                {
                    "r2_key": quote_request.video_r2_key,
                    "filename": quote_request.video_filename,
                    "size_bytes": quote_request.video_size_bytes,
                    "duration_seconds": quote_request.video_duration_seconds,
                    "mime_type": quote_request.video_mime_type,
                }
                if quote_request.video_r2_key
                else None
            ),
            "custom_quote_amount": quote_request.custom_quote_amount,
            "custom_quote_description": quote_request.custom_quote_description,
            "custom_quote_line_items": quote_request.custom_quote_line_items,
            "custom_quote_notes": quote_request.custom_quote_notes,
            "quoted_at": quote_request.quoted_at,
            "expires_at": quote_request.expires_at,
            "created_at": quote_request.created_at,
            "provider_viewed_at": quote_request.provider_viewed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get custom quote request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve request") from e


@router.post("/{request_id}/quote")
async def submit_custom_quote(
    request_id: int,
    quote_data: CustomQuoteSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider submits custom quote for a request
    """
    try:
        quote_request = (
            db.query(CustomQuoteRequest)
            .filter(
                CustomQuoteRequest.id == request_id, CustomQuoteRequest.user_id == current_user.id
            )
            .first()
        )

        if not quote_request:
            raise HTTPException(status_code=404, detail="Quote request not found")

        if quote_request.status != "pending":
            raise HTTPException(status_code=400, detail="Quote request is not pending")

        # Update quote request with custom quote
        quote_request.custom_quote_amount = quote_data.amount
        quote_request.custom_quote_description = quote_data.description
        quote_request.custom_quote_line_items = (
            [item.dict() for item in quote_data.line_items] if quote_data.line_items else None
        )
        quote_request.custom_quote_notes = quote_data.notes
        quote_request.quoted_at = datetime.utcnow()
        quote_request.status = "quoted"

        if quote_data.expires_at:
            quote_request.expires_at = quote_data.expires_at

        db.commit()
        db.refresh(quote_request)

        logger.info(f"✅ Custom quote submitted: {quote_request.id} - ${quote_data.amount}")

        # Get client
        client = db.query(Client).filter(Client.id == quote_request.client_id).first()

        # Send quote email to client
        await send_custom_quote_email(
            provider=current_user, client=client, quote_request=quote_request, db=db
        )

        return {
            "success": True,
            "quote_id": quote_request.id,
            "public_id": quote_request.public_id,
            "status": quote_request.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to submit custom quote: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to submit quote") from e


# Email Functions
async def send_custom_quote_request_notification(
    provider: User, client: Client, quote_request: CustomQuoteRequest, db: Session
):
    """Send notification to provider about new custom quote request"""
    try:
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == provider.id).first()
        )

        business_name = business_config.business_name if business_config else "Your Business"
        client_name = client.contact_name or client.business_name

        if provider.email:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
                <style type="text/css">
                    @media only screen and (max-width: 600px) {{
                        .email-container {{
                            width: 100% !important;
                            margin: 0 !important;
                        }}
                        .header-padding {{
                            padding: 30px 20px !important;
                        }}
                        .content-padding {{
                            padding: 24px 20px !important;
                        }}
                        .header-title {{
                            font-size: 24px !important;
                        }}
                        .header-icon {{
                            width: 48px !important;
                            height: 48px !important;
                        }}
                        .info-card {{
                            padding: 16px !important;
                        }}
                        .info-row {{
                            display: block !important;
                        }}
                        .info-label {{
                            display: block !important;
                            margin-bottom: 4px !important;
                            text-align: left !important;
                        }}
                        .info-value {{
                            display: block !important;
                            text-align: left !important;
                            padding-left: 0 !important;
                        }}
                        .cta-button {{
                            padding: 14px 24px !important;
                            font-size: 15px !important;
                        }}
                        .icon-container {{
                            width: 36px !important;
                            height: 36px !important;
                        }}
                    }}
                </style>
                <!--[if mso]>
                <style type="text/css">
                    table {{border-collapse: collapse; border-spacing: 0; margin: 0;}}
                    div, td {{padding: 0;}}
                    div {{margin: 0 !important;}}
                </style>
                <![endif]-->
            </head>
            <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8fafc;">
                    <tr>
                        <td style="padding: 20px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" class="email-container" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                                
                                <!-- Header -->
                                <tr>
                                    <td class="header-padding" style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 40px 30px; text-align: center;">
                                        <!-- Premium Icon using SVG -->
                                        <div style="margin-bottom: 16px;">
                                            <svg class="header-icon" width="56" height="56" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display: inline-block;">
                                                <rect width="24" height="24" rx="6" fill="white" fill-opacity="0.2"/>
                                                <path d="M9 11H15M9 15H12M7.2 20H16.8C17.9201 20 18.4802 20 18.908 19.782C19.2843 19.5903 19.5903 19.2843 19.782 18.908C20 18.4802 20 17.9201 20 16.8V7.2C20 6.0799 20 5.51984 19.782 5.09202C19.5903 4.71569 19.2843 4.40973 18.908 4.21799C18.4802 4 17.9201 4 16.8 4H7.2C6.0799 4 5.51984 4 5.09202 4.21799C4.71569 4.40973 4.40973 4.71569 4.21799 5.09202C4 5.51984 4 6.07989 4 7.2V16.8C4 17.9201 4 18.4802 4.21799 18.908C4.40973 19.2843 4.71569 19.5903 5.09202 19.782C5.51984 20 6.07989 20 7.2 20Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                            </svg>
                                        </div>
                                        <h1 class="header-title" style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; line-height: 1.3;">
                                            New Custom Quote Request
                                        </h1>
                                    </td>
                                </tr>

                                <!-- Content -->
                                <tr>
                                    <td class="content-padding" style="padding: 40px 30px;">
                                        <p style="margin: 0 0 24px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                            Hi <strong>{provider.full_name or 'there'}</strong>,
                                        </p>

                                        <p style="margin: 0 0 32px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                            <strong>{client_name}</strong> has requested a custom quote for their cleaning service.
                                        </p>

                                        <!-- Client Info Card -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8fafc; border-radius: 12px; margin-bottom: 32px; border: 1px solid #e2e8f0;">
                                            <tr>
                                                <td class="info-card" style="padding: 24px;">
                                                    <!-- Card Header -->
                                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom: 20px;">
                                                        <tr>
                                                            <td>
                                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                                    <tr>
                                                                        <td class="icon-container" style="width: 40px; height: 40px; background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); border-radius: 10px; vertical-align: middle; text-align: center;">
                                                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle;">
                                                                                <path d="M20 21C20 19.6044 20 18.9067 19.8278 18.3389C19.44 17.0605 18.4395 16.06 17.1611 15.6722C16.5933 15.5 15.8956 15.5 14.5 15.5H9.5C8.10444 15.5 7.40665 15.5 6.83886 15.6722C5.56045 16.06 4.56004 17.0605 4.17224 18.3389C4 18.9067 4 19.6044 4 21M16.5 7.5C16.5 9.98528 14.4853 12 12 12C9.51472 12 7.5 9.98528 7.5 7.5C7.5 5.01472 9.51472 3 12 3C14.4853 3 16.5 5.01472 16.5 7.5Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                            </svg>
                                                                        </td>
                                                                        <td style="padding-left: 12px; vertical-align: middle;">
                                                                            <h2 style="margin: 0; color: #00C4B4; font-size: 18px; font-weight: 600;">
                                                                                Client Information
                                                                            </h2>
                                                                        </td>
                                                                    </tr>
                                                                </table>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                    
                                                    <!-- Client Details -->
                                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                                        <tr class="info-row">
                                                            <td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; width: 35%;">Name:</td>
                                                            <td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right;">{client_name}</td>
                                                        </tr>
                                                        <tr class="info-row">
                                                            <td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; border-top: 1px solid #e2e8f0;">Email:</td>
                                                            <td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right; border-top: 1px solid #e2e8f0;">{client.email or 'N/A'}</td>
                                                        </tr>
                                                        <tr class="info-row">
                                                            <td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; border-top: 1px solid #e2e8f0;">Phone:</td>
                                                            <td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right; border-top: 1px solid #e2e8f0;">{client.phone or 'N/A'}</td>
                                                        </tr>
                                                        {f'<tr class="info-row"><td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; border-top: 1px solid #e2e8f0;">Property Type:</td><td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right; border-top: 1px solid #e2e8f0;">{client.property_type}</td></tr>' if client.property_type else ''}
                                                        {f'<tr class="info-row"><td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; border-top: 1px solid #e2e8f0;">Property Size:</td><td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right; border-top: 1px solid #e2e8f0;">{client.property_size} sqft</td></tr>' if client.property_size else ''}
                                                        {f'<tr class="info-row"><td class="info-label" style="padding: 10px 0; color: #64748b; font-size: 14px; font-weight: 600; border-top: 1px solid #e2e8f0;">Frequency:</td><td class="info-value" style="padding: 10px 0; color: #1e293b; font-size: 14px; text-align: right; border-top: 1px solid #e2e8f0;">{client.frequency}</td></tr>' if client.frequency else ''}
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>

                                        {f'''
                                        <!-- Client Notes -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; margin-bottom: 32px;">
                                            <tr>
                                                <td style="padding: 20px;">
                                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                        <tr>
                                                            <td style="vertical-align: top; padding-right: 12px;">
                                                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                    <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 13.5997 2.37562 15.1116 3.04346 16.4525C3.22094 16.8088 3.28001 17.2161 3.17712 17.6006L2.58151 19.8267C2.32295 20.793 3.20701 21.677 4.17335 21.4185L6.39939 20.8229C6.78393 20.72 7.19121 20.7791 7.54753 20.9565C8.88837 21.6244 10.4003 22 12 22Z" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                    <path d="M8 12H8.01M12 12H12.01M16 12H16.01" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                                                                </svg>
                                                            </td>
                                                            <td style="vertical-align: top;">
                                                                <p style="margin: 0 0 8px 0; color: #92400e; font-size: 14px; font-weight: 600;">Client Notes:</p>
                                                                <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.6;">{quote_request.client_notes}</p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                        ''' if quote_request.client_notes else ''}

                                        <!-- CTA Button -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom: 32px;">
                                            <tr>
                                                <td style="text-align: center;">
                                                    <a href="{FRONTEND_URL}/dashboard/custom-quotes/{quote_request.id}" class="cta-button" style="display: inline-block; background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); color: #ffffff; padding: 16px 32px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(0, 196, 180, 0.3);">
                                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="display: inline-block;">
                                                            <tr>
                                                                <td style="vertical-align: middle; padding-right: 8px;">
                                                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                        <path d="M2.42012 12.7132C2.28394 12.4975 2.21584 12.3897 2.17772 12.2234C2.14909 12.0985 2.14909 11.9015 2.17772 11.7766C2.21584 11.6103 2.28394 11.5025 2.42012 11.2868C3.54553 9.50484 6.8954 5 12.0004 5C17.1054 5 20.4553 9.50484 21.5807 11.2868C21.7169 11.5025 21.785 11.6103 21.8231 11.7766C21.8517 11.9015 21.8517 12.0985 21.8231 12.2234C21.785 12.3897 21.7169 12.4975 21.5807 12.7132C20.4553 14.4952 17.1054 19 12.0004 19C6.8954 19 3.54553 14.4952 2.42012 12.7132Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                        <path d="M12.0004 15C13.6573 15 15.0004 13.6569 15.0004 12C15.0004 10.3431 13.6573 9 12.0004 9C10.3435 9 9.0004 10.3431 9.0004 12C9.0004 13.6569 10.3435 15 12.0004 15Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                    </svg>
                                                                </td>
                                                                <td style="vertical-align: middle; color: white;">
                                                                    Review & Send Quote
                                                                </td>
                                                                <td style="vertical-align: middle; padding-left: 8px;">
                                                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                        <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                    </svg>
                                                                </td>
                                                            </tr>
                                                        </table>
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Info Box -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #dbeafe; border-left: 4px solid #3b82f6; border-radius: 8px;">
                                            <tr>
                                                <td style="padding: 16px;">
                                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                        <tr>
                                                            <td style="vertical-align: top; padding-right: 12px;">
                                                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                    <path d="M12 16V12M12 8H12.01M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12Z" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                                </svg>
                                                            </td>
                                                            <td style="vertical-align: top;">
                                                                <p style="margin: 0; color: #1e40af; font-size: 14px; line-height: 1.6;">
                                                                    <strong>Quick Tip:</strong> Respond quickly to provide excellent customer service and increase your booking rate!
                                                                </p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <!-- Footer -->
                                <tr>
                                    <td style="padding: 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                        <p style="margin: 0 0 8px 0; color: #1e293b; font-size: 16px; font-weight: 600;">
                                            Best regards,
                                        </p>
                                        <p style="margin: 0; color: #64748b; font-size: 14px;">
                                            The CleanEnroll Team
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """

            await send_email(
                to=provider.email,
                subject=f"New Custom Quote Request from {client_name}",
                title="New Custom Quote Request",
                content_html=html,
                business_config=business_config,
            )

            logger.info(f"✅ Custom quote request notification sent to {provider.email}")

    except Exception as e:
        logger.error(f"❌ Failed to send custom quote request notification: {str(e)}")


async def send_custom_quote_email(
    provider: User, client: Client, quote_request: CustomQuoteRequest, db: Session
):
    """Send custom quote to client"""
    try:
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == provider.id).first()
        )

        business_name = business_config.business_name if business_config else "Service Provider"
        client_name = client.contact_name or client.business_name

        # Build line items HTML
        line_items_html = ""
        if quote_request.custom_quote_line_items:
            line_items_html = """
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 20px 0;">
                <tr>
                    <td>
                        <h3 style="margin: 0 0 16px 0; color: #00C4B4; font-size: 16px; font-weight: 600;">Quote Breakdown:</h3>
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            """
            for item in quote_request.custom_quote_line_items:
                subtotal = item["quantity"] * item["unit_price"]
                line_items_html += f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 12px 0; color: #1e293b; font-size: 14px;">{item['name']}</td>
                    <td style="padding: 12px 0; color: #64748b; text-align: center; font-size: 14px;">{item['quantity']} × ${item['unit_price']:.2f}</td>
                    <td style="padding: 12px 0; color: #1e293b; text-align: right; font-weight: 600; font-size: 14px;">${subtotal:.2f}</td>
                </tr>
                """
            line_items_html += """
                        </table>
                    </td>
                </tr>
            </table>
            """

        expiration_html = ""
        if quote_request.expires_at:
            expiration_html = f"""
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 20px;">
                <tr>
                    <td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 16px;">
                        <p style="margin: 0; color: #92400e; font-size: 14px;">
                            <strong>⏰ Expires:</strong> {quote_request.expires_at.strftime('%B %d, %Y')}
                        </p>
                    </td>
                </tr>
            </table>
            """

        if client.email:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
                <!--[if mso]>
                <style type="text/css">
                    table {{border-collapse: collapse; border-spacing: 0; margin: 0;}}
                    div, td {{padding: 0;}}
                    div {{margin: 0 !important;}}
                </style>
                <![endif]-->
            </head>
            <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8fafc;">
                    <tr>
                        <td style="padding: 40px 20px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                                
                                <!-- Header -->
                                <tr>
                                    <td style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 40px 30px; text-align: center;">
                                        <div style="font-size: 48px; margin-bottom: 16px;">✨</div>
                                        <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; line-height: 1.3;">
                                            Your Custom Quote is Ready!
                                        </h1>
                                    </td>
                                </tr>

                                <!-- Content -->
                                <tr>
                                    <td style="padding: 40px 30px;">
                                        <p style="margin: 0 0 24px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                            Hi <strong>{client_name}</strong>,
                                        </p>

                                        <p style="margin: 0 0 32px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                            Great news! <strong>{business_name}</strong> has prepared a custom quote for your cleaning service.
                                        </p>

                                        <!-- Quote Card -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; margin-bottom: 32px; border: 2px solid #00C4B4;">
                                            <tr>
                                                <td style="padding: 32px 24px; text-align: center;">
                                                    <div style="margin-bottom: 16px;">
                                                        <span style="font-size: 40px;">💰</span>
                                                    </div>
                                                    <p style="margin: 0 0 8px 0; color: #64748b; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                        Total Quote
                                                    </p>
                                                    <p style="margin: 0 0 20px 0; color: #00C4B4; font-size: 42px; font-weight: 700; line-height: 1;">
                                                        ${quote_request.custom_quote_amount:.2f}
                                                    </p>

                                                    {f'<p style="margin: 0 0 20px 0; color: #1e293b; font-size: 15px; line-height: 1.6;"><strong>Service:</strong> {quote_request.custom_quote_description}</p>' if quote_request.custom_quote_description else ''}

                                                    {line_items_html}

                                                    {f'''
                                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #fef3c7; border-radius: 8px; margin-top: 20px;">
                                                        <tr>
                                                            <td style="padding: 16px;">
                                                                <div style="display: flex; align-items: flex-start;">
                                                                    <span style="font-size: 24px; margin-right: 12px;">📝</span>
                                                                    <div style="text-align: left;">
                                                                        <p style="margin: 0 0 8px 0; color: #92400e; font-size: 14px; font-weight: 600;">Provider Notes:</p>
                                                                        <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.6;">{quote_request.custom_quote_notes}</p>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                    ''' if quote_request.custom_quote_notes else ''}

                                                    {expiration_html}
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- CTA Button -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom: 32px;">
                                            <tr>
                                                <td style="text-align: center;">
                                                    <a href="{FRONTEND_URL}/quote/{quote_request.public_id}/approve" 
                                                       style="display: inline-block; background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); color: #ffffff; padding: 18px 40px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 18px; box-shadow: 0 4px 6px rgba(0, 196, 180, 0.3);">
                                                        Approve & Schedule →
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Next Steps -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #dbeafe; border-left: 4px solid #3b82f6; border-radius: 8px; margin-bottom: 32px;">
                                            <tr>
                                                <td style="padding: 20px;">
                                                    <div style="display: flex; align-items: flex-start;">
                                                        <span style="font-size: 24px; margin-right: 12px;">📋</span>
                                                        <div>
                                                            <p style="margin: 0 0 12px 0; color: #1e40af; font-size: 14px; font-weight: 600;">Next Steps:</p>
                                                            <ol style="margin: 0; padding-left: 20px; color: #1e40af; font-size: 14px; line-height: 1.8;">
                                                                <li>Review the quote details above</li>
                                                                <li>Click "Approve & Schedule" to continue</li>
                                                                <li>Select your preferred service date and time</li>
                                                                <li>Sign the service agreement</li>
                                                                <li>Complete payment to confirm your booking</li>
                                                            </ol>
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                        </table>

                                        <p style="margin: 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                            If you have any questions about this quote, please don't hesitate to reach out to {business_name}.
                                        </p>
                                    </td>
                                </tr>

                                <!-- Footer -->
                                <tr>
                                    <td style="padding: 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                        <p style="margin: 0 0 8px 0; color: #1e293b; font-size: 16px; font-weight: 600;">
                                            Best regards,
                                        </p>
                                        <p style="margin: 0; color: #64748b; font-size: 14px;">
                                            <strong>{business_name}</strong>
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Footer Note -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; margin: 20px auto 0;">
                                <tr>
                                    <td style="text-align: center; padding: 20px; color: #64748b; font-size: 12px; line-height: 1.6;">
                                        This quote was prepared specifically for you. Questions? Contact {business_name} directly.
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """

            await send_email(
                to=client.email,
                subject=f"Your Custom Quote from {business_name} - ${quote_request.custom_quote_amount:.2f}",
                title="Your Custom Quote is Ready!",
                content_html=html,
                business_config=business_config,
            )

            logger.info(f"✅ Custom quote email sent to {client.email}")

    except Exception as e:
        logger.error(f"❌ Failed to send custom quote email: {str(e)}")
