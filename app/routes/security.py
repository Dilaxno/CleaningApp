import base64
import hashlib
import io
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import pyotp
import qrcode
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import SECRET_KEY
from ..database import get_db
from ..email_service import send_email
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security"])


# Generate encryption key from SECRET_KEY
def get_fernet_key():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


cipher = Fernet(get_fernet_key())

# ==================== Schemas ====================


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SetupTOTPRequest(BaseModel):
    verification_code: str


class SetupPhoneRequest(BaseModel):
    phone_number: str
    verification_code: str


class SetupRecoveryEmailRequest(BaseModel):
    recovery_email: EmailStr
    verification_code: str


class SendVerificationRequest(BaseModel):
    method: str  # "phone" or "email"
    target: str  # phone number or email


class VerifyBackupCodeRequest(BaseModel):
    code: str


class SecurityStatusResponse(BaseModel):
    totp_enabled: bool
    phone_2fa_enabled: bool
    phone_number: Optional[str]
    recovery_email: Optional[str]
    recovery_email_verified: bool
    backup_codes_count: int


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: list[str]


# ==================== Helper Functions ====================


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate cryptographically secure backup codes"""
    codes = []
    charset = string.ascii_uppercase + string.digits
    for _ in range(count):
        code = "".join(secrets.choice(charset) for _ in range(4))
        code2 = "".join(secrets.choice(charset) for _ in range(4))
        codes.append(f"{code}-{code2}")
    return codes


def encrypt_backup_codes(codes: list[str]) -> list[str]:
    """Encrypt backup codes before storing"""
    return [cipher.encrypt(code.encode()).decode() for code in codes]


def decrypt_backup_codes(encrypted_codes: list[str]) -> list[str]:
    """Decrypt backup codes"""
    return [cipher.decrypt(code.encode()).decode() for code in encrypted_codes]


def generate_otp() -> str:
    """Generate 6-digit OTP using cryptographically secure random"""
    return "".join(secrets.choice(string.digits) for _ in range(6))


async def send_otp_email(email: str, otp: str):
    """Send OTP via email"""
    try:
        from ..email_templates import email_verification_template

        mjml_content = email_verification_template(user_name="there", otp=otp)

        await send_email(
            to=email,
            subject="Security Verification Code",
            mjml_content=mjml_content,
        )
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email") from e


# ==================== Endpoints ====================


@router.get("/status", response_model=SecurityStatusResponse)
async def get_security_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current security settings status"""
    backup_codes_count = len(current_user.backup_codes) if current_user.backup_codes else 0

    return SecurityStatusResponse(
        totp_enabled=current_user.totp_enabled or False,
        phone_2fa_enabled=current_user.phone_2fa_enabled or False,
        phone_number=current_user.phone_number if current_user.phone_verified else None,
        recovery_email=(
            current_user.recovery_email if current_user.recovery_email_verified else None
        ),
        recovery_email_verified=current_user.recovery_email_verified or False,
        backup_codes_count=backup_codes_count,
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Initialize TOTP setup - generate secret and QR code"""
    # Generate TOTP secret
    secret = pyotp.random_base32()

    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=current_user.email, issuer_name="CleanEnroll")

    # Create QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Generate backup codes
    backup_codes = generate_backup_codes()

    # Store secret temporarily (not enabled yet)
    current_user.totp_secret = secret
    db.commit()

    return TOTPSetupResponse(
        secret=secret, qr_code=f"data:image/png;base64,{qr_code_base64}", backup_codes=backup_codes
    )


@router.post("/totp/verify")
async def verify_and_enable_totp(
    request: SetupTOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify TOTP code and enable 2FA"""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP setup not initialized. Call /totp/setup first.",
        )

    # Verify the code
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(request.verification_code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code"
        )

    # Enable TOTP
    current_user.totp_enabled = True

    # Generate and store encrypted backup codes
    backup_codes = generate_backup_codes()
    encrypted_codes = encrypt_backup_codes(backup_codes)
    current_user.backup_codes = encrypted_codes

    db.commit()

    return {"message": "TOTP enabled successfully", "backup_codes": backup_codes}


@router.post("/totp/disable")
async def disable_totp(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Disable TOTP 2FA"""
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()

    return {"message": "TOTP disabled successfully"}


@router.post("/phone/send-verification")
async def send_phone_verification(
    request: SendVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send verification code to phone number"""
    if request.method != "phone":
        raise HTTPException(status_code=400, detail="Invalid method")

    # Generate OTP
    otp = generate_otp()

    # Store OTP temporarily
    current_user.verification_otp = otp
    current_user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    # In production, send SMS via Twilio
    # For now, log it (you'll need to configure Twilio credentials)
    logger.info(f"SMS OTP for {request.target}: {otp}")

    # TODO: Implement Twilio SMS sending
    # from twilio.rest import Client
    # client = Client(account_sid, auth_token)
    # message = client.messages.create(
    #     body=f"Your CleanEnroll verification code is: {otp}",
    #     from_=twilio_phone_number,
    #     to=request.target
    # )

    return {"message": "Verification code sent", "expires_in_minutes": 10}


@router.post("/phone/verify")
async def verify_and_enable_phone(
    request: SetupPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify phone and enable SMS 2FA"""
    # Check OTP
    if not current_user.verification_otp or not current_user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No verification code found")

    if datetime.utcnow() > current_user.otp_expires_at:
        raise HTTPException(status_code=400, detail="Verification code expired")

    if current_user.verification_otp != request.verification_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Enable phone 2FA
    current_user.phone_number = request.phone_number
    current_user.phone_verified = True
    current_user.phone_2fa_enabled = True
    current_user.verification_otp = None
    current_user.otp_expires_at = None

    db.commit()

    return {"message": "Phone 2FA enabled successfully"}


@router.post("/phone/disable")
async def disable_phone_2fa(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Disable phone 2FA"""
    current_user.phone_2fa_enabled = False
    db.commit()

    return {"message": "Phone 2FA disabled successfully"}


@router.post("/recovery-email/send-verification")
async def send_recovery_email_verification(
    request: SendVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send verification code to recovery email"""
    if request.method != "email":
        raise HTTPException(status_code=400, detail="Invalid method")

    if request.target == current_user.email:
        raise HTTPException(
            status_code=400, detail="Recovery email must be different from primary email"
        )

    # Generate OTP
    otp = generate_otp()

    # Store OTP temporarily
    current_user.verification_otp = otp
    current_user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    # Send email
    await send_otp_email(request.target, otp)

    return {"message": "Verification code sent", "expires_in_minutes": 10}


@router.post("/recovery-email/verify")
async def verify_and_set_recovery_email(
    request: SetupRecoveryEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify and set recovery email"""
    # Check OTP
    if not current_user.verification_otp or not current_user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No verification code found")

    if datetime.utcnow() > current_user.otp_expires_at:
        raise HTTPException(status_code=400, detail="Verification code expired")

    if current_user.verification_otp != request.verification_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Set recovery email
    current_user.recovery_email = request.recovery_email
    current_user.recovery_email_verified = True
    current_user.verification_otp = None
    current_user.otp_expires_at = None

    db.commit()

    return {"message": "Recovery email verified successfully"}


@router.post("/recovery-email/disable")
async def disable_recovery_email(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Disable recovery email"""
    current_user.recovery_email = None
    current_user.recovery_email_verified = False
    db.commit()

    return {"message": "Recovery email disabled successfully"}


@router.post("/backup-codes/generate")
async def generate_new_backup_codes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Generate new backup codes"""
    backup_codes = generate_backup_codes()
    encrypted_codes = encrypt_backup_codes(backup_codes)

    current_user.backup_codes = encrypted_codes
    db.commit()

    return {"message": "Backup codes generated successfully", "backup_codes": backup_codes}


@router.get("/backup-codes/view")
async def view_backup_codes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """View existing backup codes (requires re-authentication)"""
    if not current_user.backup_codes:
        raise HTTPException(status_code=404, detail="No backup codes found")

    try:
        decrypted_codes = decrypt_backup_codes(current_user.backup_codes)
        return {"backup_codes": decrypted_codes}
    except Exception as e:
        logger.error(f"Failed to decrypt backup codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve backup codes") from e


@router.delete("/backup-codes")
async def delete_backup_codes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete all backup codes"""
    current_user.backup_codes = []
    db.commit()

    return {"message": "Backup codes deleted successfully"}


@router.post("/backup-codes/verify")
async def verify_backup_code(
    request: VerifyBackupCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a backup code (used during login)"""
    if not current_user.backup_codes:
        raise HTTPException(status_code=400, detail="No backup codes available")

    try:
        decrypted_codes = decrypt_backup_codes(current_user.backup_codes)

        if request.code not in decrypted_codes:
            raise HTTPException(status_code=400, detail="Invalid backup code")

        # Remove used code
        decrypted_codes.remove(request.code)
        current_user.backup_codes = encrypt_backup_codes(decrypted_codes)
        db.commit()

        return {
            "message": "Backup code verified successfully",
            "remaining_codes": len(decrypted_codes),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify backup code: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify backup code") from e
