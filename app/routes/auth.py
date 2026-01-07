import random
import string
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models import User
from ..schemas import UserResponse, UserUpdate, MessageResponse
from ..auth import get_current_user
from ..email_service import send_email
from ..rate_limiter import create_rate_limiter

# Firebase Admin SDK for password updates
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from ..config import FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (only once)
try:
    firebase_admin.get_app()
except ValueError:
    # Initialize with project ID (uses Application Default Credentials or service account)
    try:
        # Try to initialize with default credentials
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized with default credentials")
    except Exception:
        # Initialize without credentials (limited functionality)
        firebase_admin.initialize_app(options={'projectId': FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized with project ID only")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory OTP storage (in production, use Redis or database)
otp_storage: dict = {}


class RequestOTPRequest(BaseModel):
    email: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


# Rate limiters
rate_limit_password_reset = create_rate_limiter(
    limit=5,
    window_seconds=3600,  # 1 hour
    key_prefix="password_reset",
    use_ip=True
)


@router.post("/request-otp")
async def request_password_reset_otp(
    data: RequestOTPRequest,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_password_reset)
):
    """Request OTP for password reset - Rate limited to 5 requests per hour per IP"""
    # Check if user exists
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal if email exists for security
        return {"message": "If an account exists with this email, you will receive an OTP code."}
    
    # Generate OTP
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP with expiry
    otp_storage[data.email] = {
        "otp": otp,
        "expiry": expiry,
        "attempts": 0
    }
    
    # Send OTP email
    content_html = f"""
    <p>You requested to reset your password. Use the code below to verify your identity:</p>
    <div style="background: #f8f9fb; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
      <p style="margin: 0 0 8px 0; color: #64748B; font-size: 14px;">Your verification code</p>
      <p style="margin: 0; font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #1E293B;">{otp}</p>
    </div>
    <p style="color: #64748B; font-size: 14px;">This code expires in 10 minutes.</p>
    <p style="color: #64748B; font-size: 14px;">If you didn't request this, please ignore this email.</p>
    """
    
    await send_email(
        to=data.email,
        subject="Password Reset Code - CleanEnroll",
        title="Reset Your Password",
        intro="We received a request to reset your password.",
        content_html=content_html,
    )
    
    return {"message": "If an account exists with this email, you will receive an OTP code."}


@router.post("/verify-otp")
async def verify_otp(data: VerifyOTPRequest):
    """Verify OTP code"""
    stored = otp_storage.get(data.email)
    
    if not stored:
        raise HTTPException(status_code=400, detail="No OTP request found. Please request a new code.")
    
    # Check attempts
    if stored["attempts"] >= 5:
        del otp_storage[data.email]
        raise HTTPException(status_code=400, detail="Too many attempts. Please request a new code.")
    
    # Check expiry
    if datetime.utcnow() > stored["expiry"]:
        del otp_storage[data.email]
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")
    
    # Verify OTP
    if stored["otp"] != data.otp:
        stored["attempts"] += 1
        raise HTTPException(status_code=400, detail="Invalid OTP code.")
    
    # Mark as verified (keep in storage for password reset)
    stored["verified"] = True
    
    return {"message": "OTP verified successfully", "verified": True}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password after OTP verification"""
    stored = otp_storage.get(data.email)
    
    if not stored or not stored.get("verified"):
        raise HTTPException(status_code=400, detail="Please verify OTP first.")
    
    # Check expiry again
    if datetime.utcnow() > stored["expiry"]:
        del otp_storage[data.email]
        raise HTTPException(status_code=400, detail="Session expired. Please start over.")
    
    # Verify OTP matches
    if stored["otp"] != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")
    
    # Get user
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Update password in Firebase using Admin SDK
    try:
        firebase_auth.update_user(
            user.firebase_uid,
            password=data.new_password
        )
        logger.info(f"Password updated for user: {user.email}")
    except firebase_admin.exceptions.FirebaseError as e:
        logger.error(f"Firebase password update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update password. Please try again.")
    except Exception as e:
        logger.error(f"Password update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update password. Please try again.")
    
    # Clean up OTP storage
    del otp_storage[data.email]
    
    return {
        "message": "Password reset successful",
        "success": True
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user"""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile"""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.account_type is not None:
        current_user.account_type = data.account_type
    if data.hear_about is not None:
        current_user.hear_about = data.hear_about
    
    db.commit()
    db.refresh(current_user)
    return current_user
