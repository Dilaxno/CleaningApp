"""
Email Verification Routes
Handles OTP generation, sending, and verification
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import random
import string
from ..database import get_db
from ..models import User
from ..auth import get_current_user
from ..email_service import send_email_verification_otp

router = APIRouter(prefix="/verification", tags=["verification"])


class SendOTPRequest(BaseModel):
    """Request to send OTP"""
    pass


class VerifyOTPRequest(BaseModel):
    """Request to verify OTP"""
    otp: str


class VerifyOTPResponse(BaseModel):
    """Response after OTP verification"""
    success: bool
    message: str
    email_verified: bool


def generate_otp(length: int = 6) -> str:
    """Generate a random OTP code"""
    return ''.join(random.choices(string.digits, k=length))


@router.post("/send-otp")
async def send_verification_otp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and send OTP to user's email
    """
    # current_user is already the User object from database
    user = current_user
    
    # Check if already verified
    if user.email_verified:
        return {
            "message": "Email already verified",
            "email_verified": True
        }
    
    # Generate new OTP
    otp = generate_otp(6)
    otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Save OTP to database
    user.verification_otp = otp
    user.otp_expires_at = otp_expires_at
    db.commit()
    
    # Send OTP email
    try:
        await send_email_verification_otp(
            to=user.email,
            user_name=user.full_name or "there",
            otp=otp
        )
        return {
            "message": "Verification code sent to your email",
            "email": user.email,
            "expires_in_minutes": 10
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}"
        )


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify OTP and mark email as verified
    """
    # current_user is already the User object from database
    user = current_user
    
    # Check if already verified
    if user.email_verified:
        return VerifyOTPResponse(
            success=True,
            message="Email already verified",
            email_verified=True
        )
    
    # Check if OTP exists
    if not user.verification_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code found. Please request a new code."
        )
    
    # Check if OTP expired
    if user.otp_expires_at and user.otp_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired. Please request a new code."
        )
    
    # Verify OTP
    if user.verification_otp != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please try again."
        )
    
    # Mark email as verified
    user.email_verified = True
    user.verification_otp = None
    user.otp_expires_at = None
    db.commit()
    
    return VerifyOTPResponse(
        success=True,
        message="Email verified successfully!",
        email_verified=True
    )


@router.get("/status")
async def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current email verification status
    """
    # current_user is already the User object from database
    user = current_user
    
    return {
        "email": user.email,
        "email_verified": user.email_verified,
        "has_pending_otp": user.verification_otp is not None,
        "otp_expires_at": user.otp_expires_at.isoformat() if user.otp_expires_at else None
    }
