"""
Email Routes - For testing and manual email operations
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user
from ..email_service import send_email, send_welcome_email
from ..models import User
from ..utils.sanitization import sanitize_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["Email"])


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    title: str
    content_html: str
    intro: Optional[str] = None
    cta_url: Optional[str] = None
    cta_label: Optional[str] = None


class TestEmailRequest(BaseModel):
    email_type: str  # "welcome", "test"


@router.post("/send")
async def send_custom_email(
    data: SendEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a custom email (authenticated users only)"""
    result = await send_email(
        to=data.to,
        subject=sanitize_string(data.subject),
        title=sanitize_string(data.title),
        content_html=sanitize_string(data.content_html),
        intro=sanitize_string(data.intro) if data.intro else None,
        cta_url=data.cta_url,
        cta_label=sanitize_string(data.cta_label) if data.cta_label else None,
    )
    return {"success": True, "result": result}


@router.post("/test")
async def send_test_email(
    data: TestEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a test email to the current user"""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="User has no email address")

    if data.email_type == "welcome":
        result = await send_welcome_email(
            to=current_user.email,
            user_name=current_user.full_name or "User",
        )
    else:
        result = await send_email(
            to=current_user.email,
            subject="Test Email from CleanEnroll",
            title="Test Email",
            intro="This is a test email to verify your email configuration.",
            content_html="<p>If you're seeing this, your email setup is working correctly!</p>",
            cta_url="https://cleanenroll.com/dashboard",
            cta_label="Go to Dashboard",
        )

    return {"success": True, "sent_to": current_user.email, "result": result}
