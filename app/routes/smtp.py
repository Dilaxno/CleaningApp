"""
Custom SMTP Setup Routes
Allows users to send emails from their own SMTP server
"""

import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_with_plan
from ..config import SMTP_ENCRYPTION_KEY
from ..database import get_db
from ..models import BusinessConfig, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smtp", tags=["SMTP"])

# Initialize encryption
fernet = Fernet(SMTP_ENCRYPTION_KEY) if SMTP_ENCRYPTION_KEY else None


def encrypt_password(password: str) -> str:
    """Encrypt SMTP password for storage"""
    if not fernet:
        logger.warning("SMTP_ENCRYPTION_KEY not set, storing password in plain text")
        return password
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt SMTP password for use"""
    if not fernet or not encrypted:
        return encrypted or ""
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted  # Fallback if not encrypted


class SetupSMTPRequest(BaseModel):
    email: EmailStr  # e.g., bookings@preclean.com
    host: str  # e.g., smtp.gmail.com
    port: int = 587  # 587 for TLS, 465 for SSL
    username: str
    password: str
    use_tls: bool = True


class SMTPStatusResponse(BaseModel):
    enabled: bool
    smtp_email: Optional[str]
    smtp_host: Optional[str]
    smtp_port: Optional[int]
    smtp_username: Optional[str]
    use_tls: bool
    status: Optional[str]  # live, testing, failed
    last_test_at: Optional[str]
    error_message: Optional[str]


class TestSMTPRequest(BaseModel):
    email: EmailStr
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True


def test_smtp_connection(
    host: str, port: int, username: str, password: str, from_email: str, use_tls: bool = True
) -> tuple[bool, str]:
    """
    Test SMTP connection by attempting to connect and authenticate.
    Returns (success, message)
    """
    try:
        if port == 465:
            # SSL connection
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=10)
        else:
            # TLS connection
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)

        # Authenticate
        server.login(username, password)

        # Send test email to self
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "CleanEnroll SMTP Test"
        msg["From"] = from_email
        msg["To"] = from_email

        html = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #00C4B4;">✅ SMTP Connection Successful!</h2>
            <p>Your custom email domain is now configured with CleanEnroll.</p>
            <p>All client communications will be sent from this email address.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #64748B; font-size: 12px;">This is an automated test from CleanEnroll.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        server.sendmail(from_email, from_email, msg.as_string())
        server.quit()

        logger.info(f"SMTP test successful for {from_email}")
        return True, "Connection successful! Test email sent."

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP auth error: {e}")
        return False, "Authentication failed. Check username and password."
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connect error: {e}")
        return False, f"Could not connect to {host}:{port}. Check host and port."
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"SMTP disconnected: {e}")
        return False, "Server disconnected unexpectedly. Try a different port."
    except ssl.SSLError as e:
        logger.error(f"SSL error: {e}")
        return False, "SSL/TLS error. Try toggling TLS setting or use port 465."
    except TimeoutError:
        logger.error("SMTP timeout")
        return False, "Connection timed out. Check host and port."
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False, f"Connection failed: {str(e)}"


@router.post("/test")
async def test_smtp_settings(
    request: TestSMTPRequest,
    current_user: User = Depends(get_current_user_with_plan),
):
    """Test SMTP connection without saving settings"""
    success, message = test_smtp_connection(
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        from_email=request.email,
        use_tls=request.use_tls,
    )

    return {"success": success, "message": message}


@router.post("/setup")
async def setup_smtp(
    request: SetupSMTPRequest,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """
    Setup custom SMTP for sending emails.
    Tests connection first, then saves credentials.
    """
    logger.info(f"Setting up SMTP for user {current_user.id}: {request.email}")

    # Test connection first
    success, message = test_smtp_connection(
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        from_email=request.email,
        use_tls=request.use_tls,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Get or create business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    if not config:
        config = BusinessConfig(user_id=current_user.id)
        db.add(config)

    # Save SMTP settings
    config.smtp_email = request.email
    config.smtp_host = request.host
    config.smtp_port = request.port
    config.smtp_username = request.username
    config.smtp_password = encrypt_password(request.password)
    config.smtp_use_tls = request.use_tls
    config.smtp_status = "live"
    config.smtp_last_test_at = datetime.utcnow()
    config.smtp_last_test_success = True
    config.smtp_error_message = None

    db.commit()

    logger.info(f"SMTP configured successfully for user {current_user.id}")

    return {
        "success": True,
        "message": "SMTP configured successfully! Test email sent.",
        "status": "live",
    }


@router.get("/status")
async def get_smtp_status(
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
) -> SMTPStatusResponse:
    """Get current SMTP configuration status."""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config or not config.smtp_host:
        return SMTPStatusResponse(
            enabled=False,
            smtp_email=None,
            smtp_host=None,
            smtp_port=587,
            smtp_username=None,
            use_tls=True,
            status=None,
            last_test_at=None,
            error_message=None,
        )

    return SMTPStatusResponse(
        enabled=True,
        smtp_email=config.smtp_email,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port or 587,
        smtp_username=config.smtp_username,
        use_tls=config.smtp_use_tls if config.smtp_use_tls is not None else True,
        status=config.smtp_status,
        last_test_at=config.smtp_last_test_at.isoformat() if config.smtp_last_test_at else None,
        error_message=config.smtp_error_message,
    )


@router.post("/verify")
async def verify_smtp_connection(
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Re-test existing SMTP connection (health check)"""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config or not config.smtp_host:
        raise HTTPException(status_code=404, detail="No SMTP configuration found")

    # Test connection
    success, message = test_smtp_connection(
        host=config.smtp_host,
        port=config.smtp_port or 587,
        username=config.smtp_username,
        password=decrypt_password(config.smtp_password),
        from_email=config.smtp_email,
        use_tls=config.smtp_use_tls if config.smtp_use_tls is not None else True,
    )

    # Update status
    config.smtp_last_test_at = datetime.utcnow()
    config.smtp_last_test_success = success
    config.smtp_status = "live" if success else "failed"
    config.smtp_error_message = None if success else message
    db.commit()

    return {"success": success, "status": config.smtp_status, "message": message}


@router.delete("/remove")
async def remove_smtp(
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Remove custom SMTP and revert to CleanEnroll default"""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config:
        raise HTTPException(status_code=404, detail="No configuration found")

    # Clear SMTP settings
    config.smtp_email = None
    config.smtp_host = None
    config.smtp_port = 587
    config.smtp_username = None
    config.smtp_password = None
    config.smtp_use_tls = True
    config.smtp_status = None
    config.smtp_last_test_at = None
    config.smtp_last_test_success = None
    config.smtp_error_message = None
    db.commit()

    return {"success": True, "message": "Custom SMTP removed. Using CleanEnroll default."}
