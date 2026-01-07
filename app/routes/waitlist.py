"""
Waitlist Lead Routes
Handles waitlist signups from coming-soon page
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..email_service import send_email, THEME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])

# Admin email to receive notifications
ADMIN_EMAIL = "uni.esstafasoufiane@gmail.com"


class WaitlistSignupRequest(BaseModel):
    email: EmailStr
    businessName: Optional[str] = None
    clientsPerMonth: Optional[str] = None


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    if request.client:
        return request.client.host
    
    return "unknown"


@router.post("/signup")
async def signup_waitlist(
    data: WaitlistSignupRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Add a new lead to the waitlist
    Stores in database and sends notification email
    """
    try:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:500]
        
        # Check if email already exists
        check_query = text("""
            SELECT id FROM waitlist_leads WHERE email = :email LIMIT 1
        """)
        existing = db.execute(check_query, {"email": data.email}).fetchone()
        
        if existing:
            return {
                "success": True,
                "message": "You're already on the waitlist!",
                "alreadyExists": True
            }
        
        # Insert new lead
        insert_query = text("""
            INSERT INTO waitlist_leads (
                email, business_name, clients_per_month, 
                ip_address, user_agent, source
            ) VALUES (
                :email, :business_name, :clients_per_month,
                :ip_address, :user_agent, :source
            )
            RETURNING id, created_at
        """)
        
        result = db.execute(insert_query, {
            "email": data.email,
            "business_name": data.businessName,
            "clients_per_month": data.clientsPerMonth,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "source": "coming-soon"
        })
        
        db.commit()
        row = result.fetchone()
        lead_id = row[0]
        created_at = row[1]
        
        logger.info(f"✅ New waitlist lead: ID={lead_id}, Email={data.email}")
        
        # Send notification email to admin
        try:
            await send_waitlist_notification_email(
                lead_id=lead_id,
                email=data.email,
                business_name=data.businessName,
                clients_per_month=data.clientsPerMonth,
                ip_address=ip_address,
                created_at=created_at
            )
        except Exception as email_error:
            logger.error(f"Failed to send waitlist notification email: {email_error}")
            # Don't fail the signup if email fails
        
        return {
            "success": True,
            "message": "You're on the list! We'll notify you when we launch.",
            "alreadyExists": False
        }
        
    except Exception as e:
        logger.error(f"Error adding waitlist lead: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to join waitlist")


@router.get("/count")
async def get_waitlist_count(db: Session = Depends(get_db)):
    """Get total number of waitlist signups"""
    try:
        query = text("SELECT COUNT(*) FROM waitlist_leads")
        result = db.execute(query).fetchone()
        return {"count": result[0]}
    except Exception as e:
        logger.error(f"Error getting waitlist count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get count")


async def send_waitlist_notification_email(
    lead_id: int,
    email: str,
    business_name: Optional[str],
    clients_per_month: Optional[str],
    ip_address: str,
    created_at: datetime
) -> dict:
    """Send notification email to admin when new lead joins waitlist"""
    
    content = f"""
    <p>A new lead has joined the CleanEnroll waitlist!</p>
    
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
        <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Lead Details:</h3>
        
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Lead ID</div>
            <div style="font-weight: 600; font-size: 15px; color: {THEME['text_primary']};">#{lead_id}</div>
        </div>
        
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Email</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{email}</div>
        </div>
        
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Business Name</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{business_name or 'Not provided'}</div>
        </div>
        
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Clients Per Month</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{clients_per_month or 'Not provided'}</div>
        </div>
        
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">IP Address</div>
            <div style="font-size: 15px; color: {THEME['text_muted']};">{ip_address}</div>
        </div>
        
        <div>
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Signed Up At</div>
            <div style="font-size: 15px; color: {THEME['text_muted']};">{created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </div>
    </div>
    
    <p style="color: {THEME['text_muted']}; font-size: 14px;">
        This lead came from the coming-soon landing page.
    </p>
    """
    
    return await send_email(
        to=ADMIN_EMAIL,
        subject=f"🎉 New Waitlist Lead: {email}",
        title="New Waitlist Signup!",
        intro="Someone just joined the CleanEnroll waitlist.",
        content_html=content,
    )
