"""
Email Verification Routes - Complete Rewrite
Handles OTP generation, sending, and verification with comprehensive logging
"""
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


class SendOTPRequest(BaseModel):
    """Request to send OTP - no data needed, uses current user"""
    pass


class VerifyOTPRequest(BaseModel):
    """Request to verify OTP"""
    otp: str


class VerifyOTPResponse(BaseModel):
    """Response after OTP verification"""
    success: bool
    message: str
    email_verified: bool


class VerificationStatusResponse(BaseModel):
    """Current verification status"""
    email: str
    email_verified: bool
    has_pending_otp: bool
    otp_expires_at: str | None


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code"""
    otp = ''.join(random.choices(string.digits, k=length))
    logger.debug(f"🔢 Generated OTP: {otp}")
    return otp


@router.post("/send-otp")
async def send_verification_otp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and send OTP to user's email
    Returns 200 on success, raises exception on failure
    """
    try:
        logger.info(f"📨 OTP send request for user: {current_user.email} (ID: {current_user.id})")
        
        # Check if already verified
        if current_user.email_verified:
            logger.info(f"✅ User {current_user.email} already verified, skipping OTP send")
            return {
                "success": True,
                "message": "Email already verified",
                "email_verified": True
            }
        
        # Generate new OTP
        otp = generate_otp(6)
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        logger.info(f"🔐 Generated OTP for {current_user.email}: {otp} (expires at {otp_expires_at})")
        
        # Save OTP to database
        current_user.verification_otp = otp
        current_user.otp_expires_at = otp_expires_at
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"💾 OTP saved to database for user {current_user.id}")
        logger.debug(f"📊 DB values - OTP: {current_user.verification_otp}, Expires: {current_user.otp_expires_at}")
        
        # Send OTP email
        try:
            logger.info(f"📧 Attempting to send OTP email to {current_user.email}")
            
            email_response = await send_email_verification_otp(
                to=current_user.email,
                user_name=current_user.full_name or "there",
                otp=otp
            )
            
            logger.info(f"✅ OTP email sent successfully to {current_user.email}")
            logger.debug(f"📬 Email service response: {email_response}")
            
            return {
                "success": True,
                "message": "Verification code sent to your email",
                "email": current_user.email,
                "expires_in_minutes": 10
            }
            
        except Exception as email_error:
            logger.error(f"❌ Failed to send OTP email to {current_user.email}: {str(email_error)}")
            logger.exception("Full email error traceback:")
            
            # Rollback OTP since email failed
            current_user.verification_otp = None
            current_user.otp_expires_at = None
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification email: {str(email_error)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in send_verification_otp: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
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
    try:
        logger.info(f"🔍 OTP verification request for user: {current_user.email} (ID: {current_user.id})")
        logger.debug(f"🔢 Submitted OTP: {request.otp}")
        
        # Refresh user from database to get latest data
        db.refresh(current_user)
        
        logger.debug(f"📊 Current DB state - Email verified: {current_user.email_verified}, "
                    f"OTP in DB: {current_user.verification_otp}, Expires: {current_user.otp_expires_at}")
        
        # Check if already verified
        if current_user.email_verified:
            logger.info(f"✅ User {current_user.email} already verified")
            return VerifyOTPResponse(
                success=True,
                message="Email already verified",
                email_verified=True
            )
        
        # Check if OTP exists
        if not current_user.verification_otp:
            logger.warning(f"⚠️ No OTP found for user {current_user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No verification code found. Please request a new code."
            )
        
        # Check if OTP expired
        now = datetime.utcnow()
        if current_user.otp_expires_at and current_user.otp_expires_at < now:
            logger.warning(f"⏰ OTP expired for user {current_user.email} "
                         f"(expired at {current_user.otp_expires_at}, now is {now})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Please request a new code."
            )
        
        # Verify OTP (case-sensitive, strip whitespace)
        submitted_otp = request.otp.strip()
        stored_otp = current_user.verification_otp.strip()
        
        logger.debug(f"🔐 Comparing OTPs - Submitted: '{submitted_otp}', Stored: '{stored_otp}'")
        
        if stored_otp != submitted_otp:
            logger.warning(f"❌ Invalid OTP for user {current_user.email} - "
                         f"Expected: '{stored_otp}', Got: '{submitted_otp}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Please try again."
            )
        
        logger.info(f"✅ OTP match! Marking {current_user.email} as verified")
        
        # Mark email as verified and clear OTP
        current_user.email_verified = True
        current_user.verification_otp = None
        current_user.otp_expires_at = None
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"🎉 Email verification complete for {current_user.email}")
        logger.debug(f"📊 Final DB state - Email verified: {current_user.email_verified}")
        
        return VerifyOTPResponse(
            success=True,
            message="Email verified successfully!",
            email_verified=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in verify_otp: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status", response_model=VerificationStatusResponse)
async def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current email verification status
    """
    try:
        # Refresh user from database to get latest data
        db.refresh(current_user)
        
        logger.info(f"📊 Status check for user: {current_user.email}")
        logger.debug(f"📊 Verified: {current_user.email_verified}, "
                    f"Has OTP: {current_user.verification_otp is not None}")
        
        return VerificationStatusResponse(
            email=current_user.email,
            email_verified=current_user.email_verified,
            has_pending_otp=current_user.verification_otp is not None,
            otp_expires_at=current_user.otp_expires_at.isoformat() if current_user.otp_expires_at else None
        )
    
    except Exception as e:
        logger.error(f"❌ Error getting verification status: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get verification status: {str(e)}"
        )
