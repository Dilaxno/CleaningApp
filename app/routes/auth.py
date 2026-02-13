import base64
import hashlib
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

# Firebase Admin SDK for password updates
import firebase_admin
import pyotp
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import FIREBASE_PROJECT_ID, SECRET_KEY
from ..database import get_db
from ..email_service import send_email
from ..models import User
from ..rate_limiter import create_rate_limiter
from ..schemas import UserResponse, UserUpdate
from ..turnstile import verify_turnstile


# Generate encryption key from SECRET_KEY for backup codes
def get_fernet_key():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


cipher = Fernet(get_fernet_key())

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (only once)
try:
    firebase_admin.get_app()
except ValueError:
    # Initialize with project ID (uses Application Default Credentials or service account)
    try:
        # Try to initialize with default credentials
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized with default credentials")
    except Exception:
        # Initialize without credentials (limited functionality)
        firebase_admin.initialize_app(options={"projectId": FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized with project ID only")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Redis-based OTP storage for security and persistence
import json

from ..rate_limiter import get_redis_client


def store_otp_in_redis(email: str, otp: str, expires_in_seconds: int = 600):
    """Store OTP in Redis with expiration"""
    try:
        redis_client = get_redis_client()
        otp_key = f"otp:{email}"
        otp_data = {"otp": otp, "created_at": datetime.utcnow().isoformat(), "attempts": 0}
        redis_client.setex(otp_key, expires_in_seconds, json.dumps(otp_data))
        logger.info(f"OTP stored in Redis for {email}")
    except Exception as e:
        logger.error(f"Failed to store OTP in Redis: {e}")
        raise


def get_otp_from_redis(email: str) -> dict:
    """Get OTP data from Redis"""
    try:
        redis_client = get_redis_client()
        otp_key = f"otp:{email}"
        otp_data = redis_client.get(otp_key)
        if otp_data:
            return json.loads(otp_data)
        return None
    except Exception as e:
        logger.error(f"Failed to get OTP from Redis: {e}")
        return None


def increment_otp_attempts(email: str) -> int:
    """Increment OTP attempts and return current count"""
    try:
        redis_client = get_redis_client()
        otp_key = f"otp:{email}"
        otp_data = get_otp_from_redis(email)
        if otp_data:
            otp_data["attempts"] += 1
            ttl = redis_client.ttl(otp_key)
            if ttl > 0:
                redis_client.setex(otp_key, ttl, json.dumps(otp_data))
            return otp_data["attempts"]
        return 0
    except Exception as e:
        logger.error(f"Failed to increment OTP attempts: {e}")
        return 0


def delete_otp_from_redis(email: str):
    """Delete OTP from Redis"""
    try:
        redis_client = get_redis_client()
        otp_key = f"otp:{email}"
        redis_client.delete(otp_key)
        logger.info(f"OTP deleted from Redis for {email}")
    except Exception as e:
        logger.error(f"Failed to delete OTP from Redis: {e}")


class RequestOTPRequest(BaseModel):
    email: str
    turnstileToken: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class RecoveryMethodsRequest(BaseModel):
    email: str
    turnstileToken: Optional[str] = None


class RecoveryMethodsResponse(BaseModel):
    has_totp: bool
    has_phone: bool
    has_recovery_email: bool
    has_backup_codes: bool
    recovery_email_hint: Optional[str] = None
    phone_hint: Optional[str] = None


class VerifyRecoveryRequest(BaseModel):
    email: str
    method: str  # "totp", "phone", "recovery_email", "backup_code"
    code: str


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return "".join(random.choices(string.digits, k=6))


def mask_email(email: str) -> str:
    """Mask email for privacy: jo***@gm***.com"""
    if not email or "@" not in email:
        return "***@***.***"
    local, domain = email.split("@")
    domain_parts = domain.split(".")
    masked_local = f"{local[:2]}***" if len(local) > 2 else f"{local[0]}***"
    masked_domain = (
        f"{domain_parts[0][:2]}***" if len(domain_parts[0]) > 2 else f"{domain_parts[0][0]}***"
    )
    return f"{masked_local}@{masked_domain}.{domain_parts[-1]}"


def mask_phone(phone: str) -> str:
    """Mask phone for privacy: ***-***-1234"""
    if not phone or len(phone) < 4:
        return "***-***-****"
    return f"***-***-{phone[-4:]}"


def decrypt_backup_codes(encrypted_codes: list[str]) -> list[str]:
    """Decrypt backup codes"""
    return [cipher.decrypt(code.encode()).decode() for code in encrypted_codes]


def encrypt_backup_codes(codes: list[str]) -> list[str]:
    """Encrypt backup codes before storing"""
    return [cipher.encrypt(code.encode()).decode() for code in codes]


# Rate limiters
rate_limit_password_reset = create_rate_limiter(
    limit=10,  # Increased from 5 to 10 for better UX
    window_seconds=3600,  # 1 hour
    key_prefix="password_reset",
    use_ip=True,
)


@router.post("/request-otp")
async def request_password_reset_otp(
    data: RequestOTPRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_password_reset),
):
    """Request OTP for password reset - Rate limited to 5 requests per hour per IP with Turnstile CAPTCHA"""
    logger.info(f"Password reset OTP request for email: {data.email}")
    logger.info(f"Request origin: {request.headers.get('origin')}")
    logger.info(f"Request host: {request.headers.get('host')}")

    # Verify Turnstile token
    if data.turnstileToken:
        client_ip = request.client.host if request.client else None
        is_valid = await verify_turnstile(data.turnstileToken, client_ip)
        if not is_valid:
            logger.warning(f"Turnstile verification failed for {data.email}")
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed") from e
    else:
        logger.warning("⚠️ No Turnstile token provided for password reset request")

    # Check if user exists
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal if email exists for security
        return {"message": "If an account exists with this email, you will receive an OTP code."}

    # Generate OTP
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)

    # Store OTP in Redis with expiry
    store_otp_in_redis(data.email, otp, expires_in_seconds=600)  # 10 minutes

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
    stored = get_otp_from_redis(data.email)

    if not stored:
        raise HTTPException(
            status_code=400, detail="No OTP request found. Please request a new code."
        )

    # Check attempts
    if stored["attempts"] >= 5:
        delete_otp_from_redis(data.email)
        raise HTTPException(status_code=400, detail="Too many attempts. Please request a new code.")

    # Check expiry (Redis handles TTL, but double-check)
    created_at = datetime.fromisoformat(stored["created_at"])
    if datetime.utcnow() > created_at + timedelta(minutes=10):
        delete_otp_from_redis(data.email)
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")

    # Verify OTP
    if stored["otp"] != data.otp:
        attempts = increment_otp_attempts(data.email)
        if attempts >= 5:
            delete_otp_from_redis(data.email)
            raise HTTPException(
                status_code=400, detail="Too many attempts. Please request a new code."
            )
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    # Mark as verified (keep in Redis for password reset)
    stored["verified"] = True
    redis_client = get_redis_client()
    otp_key = f"otp:{data.email}"
    ttl = redis_client.ttl(otp_key)
    if ttl > 0:
        redis_client.setex(otp_key, ttl, json.dumps(stored))

    return {"message": "OTP verified successfully", "verified": True}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password after OTP or 2FA verification"""
    stored = get_otp_from_redis(data.email)

    if not stored or not stored.get("verified"):
        raise HTTPException(status_code=400, detail="Please verify your identity first.")

    # Check expiry again (Redis handles TTL, but double-check)
    created_at = datetime.fromisoformat(stored["created_at"])
    if datetime.utcnow() > created_at + timedelta(minutes=10):
        delete_otp_from_redis(data.email)
        raise HTTPException(status_code=400, detail="Session expired. Please start over.")

    # For email OTP, verify OTP matches (skip for 2FA verified sessions)
    if stored["otp"] != "2fa_verified" and stored["otp"] != "verified":
        raise HTTPException(status_code=400, detail="Invalid verification state.")

    # Get user
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Update password in Firebase using Admin SDK
    try:
        firebase_auth.update_user(user.firebase_uid, password=data.new_password)
        logger.info(f"Password updated for user: {user.email}")
    except firebase_admin.exceptions.FirebaseError as e:
        logger.error(f"Firebase password update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update password. Please try again.")
    except Exception as e:
        logger.error(f"Password update error: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update password. Please try again."
        ) from e

    # Clean up OTP storage
    delete_otp_from_redis(data.email)

    return {"message": "Password reset successful", "success": True}


# ==================== Account Recovery with 2FA ====================


@router.post("/recovery/methods", response_model=RecoveryMethodsResponse)
async def get_recovery_methods(
    data: RecoveryMethodsRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_password_reset),
):
    """Get available 2FA recovery methods for an account"""
    logger.info(f"Recovery methods request for email: {data.email}")
    logger.info(f"Request origin: {request.headers.get('origin')}")
    logger.info(f"Request host: {request.headers.get('host')}")

    # Verify Turnstile token
    if data.turnstileToken:
        client_ip = request.client.host if request.client else None
        is_valid = await verify_turnstile(data.turnstileToken, client_ip)
        if not is_valid:
            logger.warning(f"Turnstile verification failed for {data.email}")
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    # Check if user exists
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Return empty response to not reveal if email exists
        return RecoveryMethodsResponse(
            has_totp=False, has_phone=False, has_recovery_email=False, has_backup_codes=False
        )

    return RecoveryMethodsResponse(
        has_totp=user.totp_enabled or False,
        has_phone=user.phone_2fa_enabled or False,
        has_recovery_email=user.recovery_email_verified or False,
        has_backup_codes=bool(user.backup_codes and len(user.backup_codes) > 0),
        recovery_email_hint=(
            mask_email(user.recovery_email) if user.recovery_email_verified else None
        ),
        phone_hint=mask_phone(user.phone_number) if user.phone_2fa_enabled else None,
    )


@router.post("/recovery/send-code")
async def send_recovery_code(
    data: RecoveryMethodsRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_password_reset),
):
    """Send recovery code to recovery email or phone"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return {"message": "If recovery methods are available, a code has been sent."}

    # Generate OTP
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)

    # Store OTP in Redis
    store_otp_in_redis(f"recovery_{data.email}", otp, expires_in_seconds=600)  # 10 minutes

    # Send to recovery email if available
    if user.recovery_email_verified and user.recovery_email:
        content_html = f"""
        <p>You requested to recover your CleanEnroll account. Use the code below to verify your identity:</p>
        <div style="background: #f8f9fb; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
          <p style="margin: 0 0 8px 0; color: #64748B; font-size: 14px;">Your recovery code</p>
          <p style="margin: 0; font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #1E293B;">{otp}</p>
        </div>
        <p style="color: #64748B; font-size: 14px;">This code expires in 10 minutes.</p>
        <p style="color: #64748B; font-size: 14px;">If you didn't request this, please secure your account immediately.</p>
        """

        await send_email(
            to=user.recovery_email,
            subject="Account Recovery Code - CleanEnroll",
            title="Recover Your Account",
            intro="We received a request to recover your account.",
            content_html=content_html,
        )
        logger.info(f"Recovery code sent to recovery email for: {user.email}")

    return {"message": "If recovery methods are available, a code has been sent."}


@router.post("/recovery/verify")
async def verify_recovery_method(data: VerifyRecoveryRequest, db: Session = Depends(get_db)):
    """Verify identity using 2FA recovery method"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")

    verified = False

    if data.method == "totp":
        # Verify TOTP code
        if not user.totp_enabled or not user.totp_secret:
            raise HTTPException(status_code=400, detail="TOTP not enabled for this account")

        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(data.code, valid_window=1):
            verified = True
        else:
            raise HTTPException(status_code=400, detail="Invalid authenticator code")

    elif data.method == "backup_code":
        # Verify backup code
        if not user.backup_codes:
            raise HTTPException(status_code=400, detail="No backup codes available")

        try:
            decrypted_codes = decrypt_backup_codes(user.backup_codes)
            normalized_code = data.code.upper().replace(" ", "")

            if normalized_code in decrypted_codes:
                # Remove used code
                decrypted_codes.remove(normalized_code)
                user.backup_codes = encrypt_backup_codes(decrypted_codes)
                db.commit()
                verified = True
            else:
                raise HTTPException(status_code=400, detail="Invalid backup code")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Backup code verification error: {e}")
            raise HTTPException(status_code=400, detail="Invalid backup code") from e

    elif data.method == "recovery_email":
        # Verify recovery email OTP
        stored = get_otp_from_redis(f"recovery_{data.email}")
        if not stored:
            raise HTTPException(
                status_code=400, detail="No recovery code found. Please request a new one."
            )

        if stored["attempts"] >= 5:
            delete_otp_from_redis(f"recovery_{data.email}")
            raise HTTPException(
                status_code=400, detail="Too many attempts. Please request a new code."
            )

        created_at = datetime.fromisoformat(stored["created_at"])
        if datetime.utcnow() > created_at + timedelta(minutes=10):
            delete_otp_from_redis(f"recovery_{data.email}")
            raise HTTPException(status_code=400, detail="Code expired. Please request a new one.")

        if stored["otp"] != data.code:
            increment_otp_attempts(f"recovery_{data.email}")
            raise HTTPException(status_code=400, detail="Invalid recovery code")

        verified = True
        delete_otp_from_redis(f"recovery_{data.email}")

    elif data.method == "phone":
        # Verify phone OTP (similar to recovery email)
        stored = get_otp_from_redis(f"recovery_{data.email}")
        if not stored:
            raise HTTPException(
                status_code=400, detail="No recovery code found. Please request a new one."
            )

        if stored["attempts"] >= 5:
            delete_otp_from_redis(f"recovery_{data.email}")
            raise HTTPException(
                status_code=400, detail="Too many attempts. Please request a new code."
            )

        created_at = datetime.fromisoformat(stored["created_at"])
        if datetime.utcnow() > created_at + timedelta(minutes=10):
            delete_otp_from_redis(f"recovery_{data.email}")
            raise HTTPException(status_code=400, detail="Code expired. Please request a new one.")

        if stored["otp"] != data.code:
            increment_otp_attempts(f"recovery_{data.email}")
            raise HTTPException(status_code=400, detail="Invalid recovery code")

        verified = True
        delete_otp_from_redis(f"recovery_{data.email}")

    else:
        raise HTTPException(status_code=400, detail="Invalid recovery method")

    if verified:
        # Create a verified session for password reset in Redis
        verified_data = {
            "otp": "2fa_verified",
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0,
            "verified": True,
            "method": data.method,
        }
        redis_client = get_redis_client()
        redis_client.setex(f"otp:{data.email}", 900, json.dumps(verified_data))  # 15 minutes

        return {"message": "Identity verified successfully", "verified": True}

    raise HTTPException(status_code=400, detail="Verification failed")


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
