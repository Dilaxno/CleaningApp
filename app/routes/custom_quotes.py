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

        # Business name available for future email customization
        client_name = client.contact_name or client.business_name

        if provider.email:
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">📋 New Custom Quote Request</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {provider.full_name or 'there'},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        <strong>{client_name}</strong> has requested a custom quote for their cleaning service.
                    </p>

                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                        <h2 style="color: #3b82f6; font-size: 18px; margin-top: 0; margin-bottom: 15px;">
                            Client Information
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Name:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Email:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.email or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Phone:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.phone or 'N/A'}</td>
                            </tr>
                            {f'<tr><td style="padding: 8px 0; color: #64748b; font-weight: 600;">Property Type:</td><td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.property_type}</td></tr>' if client.property_type else ''}
                            {f'<tr><td style="padding: 8px 0; color: #64748b; font-weight: 600;">Property Size:</td><td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.property_size} sqft</td></tr>' if client.property_size else ''}
                            {f'<tr><td style="padding: 8px 0; color: #64748b; font-weight: 600;">Frequency:</td><td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.frequency}</td></tr>' if client.frequency else ''}
                        </table>
                    </div>

                    {f'<div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 25px; border-radius: 4px;"><p style="margin: 0; color: #92400e; font-size: 14px;"><strong>Client Notes:</strong><br>{quote_request.client_notes}</p></div>' if quote_request.client_notes else ''}

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{FRONTEND_URL}/dashboard/custom-quotes/{quote_request.id}"
                           style="display: inline-block; background: #3b82f6; color: white; padding: 14px 28px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                            Review & Send Quote →
                        </a>
                    </div>

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                        Respond quickly to provide excellent customer service!
                    </p>
                </div>
            </div>
            """

            await send_email(
                to=provider.email,
                subject=f"New Custom Quote Request from {client_name}",
                html_content=html,
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
            line_items_html = "<div style='margin: 20px 0;'><h3 style='color: #00C4B4; font-size: 16px; margin-bottom: 10px;'>Quote Breakdown:</h3><table style='width: 100%; border-collapse: collapse;'>"
            for item in quote_request.custom_quote_line_items:
                subtotal = item["quantity"] * item["unit_price"]
                line_items_html += f"""
                <tr style='border-bottom: 1px solid #e5e7eb;'>
                    <td style='padding: 8px 0; color: #1e293b;'>{item['name']}</td>
                    <td style='padding: 8px 0; color: #64748b; text-align: center;'>{item['quantity']} × ${item['unit_price']:.2f}</td>
                    <td style='padding: 8px 0; color: #1e293b; text-align: right; font-weight: 600;'>${subtotal:.2f}</td>
                </tr>
                """
            line_items_html += "</table></div>"

        expiration_html = ""
        if quote_request.expires_at:
            expiration_html = f"<p style='color: #f59e0b; font-size: 14px; margin-top: 15px;'>⏰ This quote expires on {quote_request.expires_at.strftime('%B %d, %Y')}</p>"

        if client.email:
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Your Custom Quote is Ready! 📋</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {client_name},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        Great news! <strong>{business_name}</strong> has prepared a custom quote for your cleaning service.
                    </p>

                    <div style="background: #f0fdf4; padding: 25px; border-radius: 12px; margin-bottom: 25px; border-left: 4px solid #00C4B4;">
                        <div style="text-align: center; margin-bottom: 15px;">
                            <p style="color: #64748b; font-size: 14px; margin: 0;">Total Quote</p>
                            <p style="color: #00C4B4; font-size: 36px; font-weight: bold; margin: 10px 0;">${quote_request.custom_quote_amount:.2f}</p>
                        </div>

                        {f'<p style="color: #1e293b; font-size: 15px; margin: 15px 0;"><strong>Service:</strong> {quote_request.custom_quote_description}</p>' if quote_request.custom_quote_description else ''}

                        {line_items_html}

                        {f'<div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin-top: 20px;"><p style="margin: 0; color: #92400e; font-size: 14px;"><strong>Provider Notes:</strong><br>{quote_request.custom_quote_notes}</p></div>' if quote_request.custom_quote_notes else ''}

                        {expiration_html}
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{FRONTEND_URL}/quote/{quote_request.public_id}/approve"
                           style="display: inline-block; background: #00C4B4; color: white; padding: 16px 32px;
                                  text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 18px; box-shadow: 0 4px 6px rgba(0, 196, 180, 0.3);">
                            Approve & Schedule →
                        </a>
                    </div>

                    <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                            <strong>Next Steps:</strong><br>
                            1. Review the quote details above<br>
                            2. Click "Approve & Schedule" to continue<br>
                            3. Select your preferred service date and time<br>
                            4. Sign the service agreement<br>
                            5. Complete payment to confirm your booking
                        </p>
                    </div>

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                        If you have any questions about this quote, please don't hesitate to reach out to {business_name}.
                    </p>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>{business_name}</strong>
                    </p>
                </div>

                <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px;">
                    <p style="margin: 0;">
                        This quote was prepared specifically for you. Questions? Contact {business_name} directly.
                    </p>
                </div>
            </div>
            """

            await send_email(
                to=client.email,
                subject=f"Your Custom Quote from {business_name} - ${quote_request.custom_quote_amount:.2f}",
                html_content=html,
                business_config=business_config,
            )

            logger.info(f"✅ Custom quote email sent to {client.email}")

    except Exception as e:
        logger.error(f"❌ Failed to send custom quote email: {str(e)}")
