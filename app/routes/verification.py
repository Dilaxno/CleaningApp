"""
Email Verification Routes - Complete Rewrite
Handles OTP generation, sending, and verification with comprehensive logging
"""

import logging
import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..email_service import send_email_verification_otp
from ..models import User

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


class RequestEmailChangeRequest(BaseModel):
    """Request to change email"""

    new_email: str


class VerifyEmailChangeRequest(BaseModel):
    """Verify OTP and complete email change"""

    otp: str
    new_email: str


class EmailChangeResponse(BaseModel):
    """Response after email change"""

    success: bool
    message: str
    new_email: str


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure random numeric OTP code"""
    otp = "".join(secrets.choice(string.digits) for _ in range(length))
    logger.debug(f"🔢 Generated OTP: {otp}")
    return otp


@router.post("/send-otp")
async def send_verification_otp(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Generate and send OTP to user's email
    Returns 200 on success, raises exception on failure
    """
    try:
        logger.info(f"📨 OTP send request for user: {current_user.email} (ID: {current_user.id})")

        # Check if already verified
        if current_user.email_verified:
            return {"success": True, "message": "Email already verified", "email_verified": True}

        # Generate new OTP
        otp = generate_otp(6)
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        # Save OTP to database
        current_user.verification_otp = otp
        current_user.otp_expires_at = otp_expires_at
        db.commit()
        db.refresh(current_user)

        logger.info(f"💾 OTP saved to database for user {current_user.id}")
        logger.debug(
            f"📊 DB values - OTP: {current_user.verification_otp}, Expires: {current_user.otp_expires_at}"
        )

        # Send OTP email
        try:
            email_response = await send_email_verification_otp(
                to=current_user.email, user_name=current_user.full_name or "there", otp=otp
            )
            logger.debug(f"📬 Email service response: {email_response}")

            return {
                "success": True,
                "message": "Verification code sent to your email",
                "email": current_user.email,
                "expires_in_minutes": 10,
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
                detail=f"Failed to send verification email: {str(email_error)}",
            ) from email_error

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in send_verification_otp: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify OTP and mark email as verified
    """
    try:
        logger.info(
            f"🔍 OTP verification request for user: {current_user.email} (ID: {current_user.id})"
        )
        logger.debug(f"🔢 Submitted OTP: {request.otp}")

        # Refresh user from database to get latest data
        db.refresh(current_user)

        logger.debug(
            f"📊 Current DB state - Email verified: {current_user.email_verified}, "
            f"OTP in DB: {current_user.verification_otp}, Expires: {current_user.otp_expires_at}"
        )

        # Check if already verified
        if current_user.email_verified:
            return VerifyOTPResponse(
                success=True, message="Email already verified", email_verified=True
            )

        # Check if OTP exists
        if not current_user.verification_otp:
            logger.warning(f"⚠️ No OTP found for user {current_user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No verification code found. Please request a new code.",
            )

        # Check if OTP expired
        now = datetime.utcnow()
        if current_user.otp_expires_at and current_user.otp_expires_at < now:
            logger.warning(
                f"⏰ OTP expired for user {current_user.email} "
                f"(expired at {current_user.otp_expires_at}, now is {now})"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Please request a new code.",
            )

        # Verify OTP (case-sensitive, strip whitespace)
        submitted_otp = request.otp.strip()
        stored_otp = current_user.verification_otp.strip()

        logger.debug(f"🔐 Comparing OTPs - Submitted: '{submitted_otp}', Stored: '{stored_otp}'")

        if stored_otp != submitted_otp:
            logger.warning(
                f"❌ Invalid OTP for user {current_user.email} - "
                f"Expected: '{stored_otp}', Got: '{submitted_otp}'"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Please try again.",
            )
        # Mark email as verified and clear OTP
        current_user.email_verified = True
        current_user.verification_otp = None
        current_user.otp_expires_at = None
        db.commit()
        db.refresh(current_user)

        logger.info(f"🎉 Email verification complete for {current_user.email}")
        logger.debug(f"📊 Final DB state - Email verified: {current_user.email_verified}")

        return VerifyOTPResponse(
            success=True, message="Email verified successfully!", email_verified=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in verify_otp: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/request-email-change")
async def request_email_change(
    request: RequestEmailChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate email change by sending OTP to new email address
    """
    try:
        new_email = request.new_email.strip().lower()
        # Validate new email is different
        if new_email == current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New email must be different from current email",
            )

        # Check if new email is already in use
        existing_user = db.query(User).filter(User.email == new_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already registered to another account",
            )

        # Generate OTP for email change
        otp = generate_otp(6)
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        # Store pending email change info
        current_user.pending_email = new_email
        current_user.verification_otp = otp
        current_user.otp_expires_at = otp_expires_at
        db.commit()
        db.refresh(current_user)

        logger.info(f"💾 Pending email change saved for user {current_user.id}")

        # Send OTP to new email
        try:
            from ..email_service import send_email

            content = f"""
            <p>Hi {current_user.full_name or 'there'},</p>
            <p>You requested to change your email address to <strong>{new_email}</strong>.</p>
            <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
              <p style="color: #64748b; font-size: 14px; margin-bottom: 12px;">Your verification code is:</p>
              <div style="font-size: 36px; font-weight: bold; color: #00C4B4; letter-spacing: 8px; font-family: monospace;">
                {otp}
              </div>
              <p style="color: #64748b; font-size: 13px; margin-top: 12px;">This code expires in 10 minutes</p>
            </div>
            <p style="color: #64748b; font-size: 14px;">
              If you didn't request this change, please ignore this email or contact support if you're concerned.
            </p>
            """

            await send_email(
                to=new_email,
                subject="Verify Your New Email Address",
                title="Email Change Verification",
                content_html=content,
            )
            return {
                "success": True,
                "message": f"Verification code sent to {new_email}",
                "expires_in_minutes": 10,
            }

        except Exception as email_error:
            logger.error(f"❌ Failed to send OTP to {new_email}: {str(email_error)}")

            # Rollback pending email change
            current_user.pending_email = None
            current_user.verification_otp = None
            current_user.otp_expires_at = None
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification email: {str(email_error)}",
            ) from email_error

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in request_email_change: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/verify-email-change", response_model=EmailChangeResponse)
async def verify_email_change(
    request: VerifyEmailChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify OTP and complete email change
    """
    try:
        new_email = request.new_email.strip().lower()

        logger.info(f"🔍 Email change verification for user {current_user.email} to {new_email}")

        # Refresh user from database
        db.refresh(current_user)

        # Check if there's a pending email change
        if not current_user.pending_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No pending email change found"
            )

        # Verify the new email matches pending
        if current_user.pending_email != new_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email does not match pending change request",
            )

        # Check if OTP exists
        if not current_user.verification_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No verification code found. Please request a new code.",
            )

        # Check if OTP expired
        now = datetime.utcnow()
        if current_user.otp_expires_at and current_user.otp_expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Please request a new code.",
            )

        # Verify OTP
        submitted_otp = request.otp.strip()
        stored_otp = current_user.verification_otp.strip()

        if stored_otp != submitted_otp:
            logger.warning("❌ Invalid OTP for email change")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Please try again.",
            )
        # Update email and clear pending change
        old_email = current_user.email
        current_user.email = new_email
        current_user.pending_email = None
        current_user.verification_otp = None
        current_user.otp_expires_at = None
        current_user.email_verified = True  # New email is now verified
        db.commit()
        db.refresh(current_user)

        logger.info(f"🎉 Email successfully changed from {old_email} to {new_email}")

        return EmailChangeResponse(
            success=True, message="Email changed successfully!", new_email=new_email
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in verify_email_change: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/status", response_model=VerificationStatusResponse)
async def get_verification_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get current email verification status
    """
    try:
        # Refresh user from database to get latest data
        db.refresh(current_user)
        logger.debug(
            f"📊 Verified: {current_user.email_verified}, "
            f"Has OTP: {current_user.verification_otp is not None}"
        )

        return VerificationStatusResponse(
            email=current_user.email,
            email_verified=current_user.email_verified,
            has_pending_otp=current_user.verification_otp is not None,
            otp_expires_at=(
                current_user.otp_expires_at.isoformat() if current_user.otp_expires_at else None
            ),
        )

    except Exception as e:
        logger.error(f"❌ Error getting verification status: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get verification status: {str(e)}",
        ) from e
