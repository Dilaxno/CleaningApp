"""
Twilio SMS Integration Routes
Handles Twilio credential management and SMS sending
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user_with_plan
from ..config import SECRET_KEY
from ..database import get_db
from ..models import User
from ..models_twilio import TwilioIntegration, TwilioSMSLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["twilio"])

# Encryption for credentials
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))


# Pydantic Models
class TwilioStatusResponse(BaseModel):
    connected: bool
    sms_enabled: Optional[bool] = None
    phone_number: Optional[str] = None
    is_verified: Optional[bool] = None
    send_estimate_approval: Optional[bool] = None
    send_schedule_confirmation: Optional[bool] = None
    send_contract_signed: Optional[bool] = None
    send_job_reminder: Optional[bool] = None
    send_job_completion: Optional[bool] = None
    send_payment_confirmation: Optional[bool] = None


class TwilioCredentials(BaseModel):
    account_sid: str
    auth_token: str
    messaging_service_sid: Optional[str] = None
    phone_number: Optional[str] = None


class TwilioSettings(BaseModel):
    sms_enabled: bool
    send_estimate_approval: bool
    send_schedule_confirmation: bool
    send_contract_signed: bool
    send_job_reminder: bool
    send_job_completion: bool
    send_payment_confirmation: bool


class TestSMSRequest(BaseModel):
    phone_number: str


# Helper Functions
def encrypt_credential(credential: str) -> str:
    """Encrypt a credential for storage"""
    return cipher_suite.encrypt(credential.encode()).decode()


def decrypt_credential(encrypted_credential: str) -> str:
    """Decrypt a stored credential"""
    return cipher_suite.decrypt(encrypted_credential.encode()).decode()


async def verify_twilio_credentials(
    account_sid: str, auth_token: str
) -> tuple[bool, Optional[str]]:
    """Verify Twilio credentials by making a test API call"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                auth=(account_sid, auth_token),
                timeout=10.0,
            )

            if response.status_code == 200:
                return True, None
            elif response.status_code == 401:
                return False, "Invalid Account SID or Auth Token"
            else:
                return False, f"Verification failed: {response.status_code}"
    except Exception as e:
        logger.error(f"Twilio verification error: {str(e)}")
        return False, f"Connection error: {str(e)}"


# Routes
@router.get("/status", response_model=TwilioStatusResponse)
async def get_twilio_status(
    current_user: User = Depends(get_current_user_with_plan), db: Session = Depends(get_db)
):
    """Get Twilio integration status"""
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if not integration:
        return TwilioStatusResponse(connected=False)

    # Mask phone number for display
    phone_display = None
    if integration.phone_number:
        phone_display = f"***-***-{integration.phone_number[-4:]}"

    return TwilioStatusResponse(
        connected=True,
        sms_enabled=integration.sms_enabled,
        phone_number=phone_display,
        is_verified=integration.is_verified,
        send_estimate_approval=integration.send_estimate_approval,
        send_schedule_confirmation=integration.send_schedule_confirmation,
        send_contract_signed=integration.send_contract_signed,
        send_job_reminder=integration.send_job_reminder,
        send_job_completion=integration.send_job_completion,
        send_payment_confirmation=integration.send_payment_confirmation,
    )


@router.post("/connect")
async def connect_twilio(
    credentials: TwilioCredentials,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Connect Twilio account with credentials"""
    # Validate that either messaging_service_sid or phone_number is provided
    if not credentials.messaging_service_sid and not credentials.phone_number:
        raise HTTPException(
            status_code=400,
            detail="Either Messaging Service SID or Phone Number must be provided",
        )

    # Verify credentials
    is_valid, error_message = await verify_twilio_credentials(
        credentials.account_sid, credentials.auth_token
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message or "Invalid credentials")

    # Check if integration already exists
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if integration:
        # Update existing integration
        integration.account_sid = encrypt_credential(credentials.account_sid)
        integration.auth_token = encrypt_credential(credentials.auth_token)
        integration.messaging_service_sid = (
            encrypt_credential(credentials.messaging_service_sid)
            if credentials.messaging_service_sid
            else None
        )
        integration.phone_number = credentials.phone_number
        integration.is_verified = True
        integration.updated_at = datetime.utcnow()
    else:
        # Create new integration
        integration = TwilioIntegration(
            user_id=current_user.id,
            account_sid=encrypt_credential(credentials.account_sid),
            auth_token=encrypt_credential(credentials.auth_token),
            messaging_service_sid=(
                encrypt_credential(credentials.messaging_service_sid)
                if credentials.messaging_service_sid
                else None
            ),
            phone_number=credentials.phone_number,
            is_verified=True,
            sms_enabled=True,
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)

    logger.info(f"Twilio integration connected for user {current_user.id}")

    return {"message": "Twilio connected successfully", "verified": True}


@router.post("/disconnect")
async def disconnect_twilio(
    current_user: User = Depends(get_current_user_with_plan), db: Session = Depends(get_db)
):
    """Disconnect Twilio integration"""
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Twilio integration not found")

    db.delete(integration)
    db.commit()

    logger.info(f"Twilio integration disconnected for user {current_user.id}")

    return {"message": "Twilio disconnected successfully"}


@router.put("/settings")
async def update_twilio_settings(
    settings: TwilioSettings,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Update Twilio SMS notification settings"""
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Twilio integration not found")

    # Update settings
    integration.sms_enabled = settings.sms_enabled
    integration.send_estimate_approval = settings.send_estimate_approval
    integration.send_schedule_confirmation = settings.send_schedule_confirmation
    integration.send_contract_signed = settings.send_contract_signed
    integration.send_job_reminder = settings.send_job_reminder
    integration.send_job_completion = settings.send_job_completion
    integration.send_payment_confirmation = settings.send_payment_confirmation
    integration.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Twilio settings updated for user {current_user.id}")

    return {"message": "Settings updated successfully"}


@router.post("/test-sms")
async def send_test_sms(
    request: TestSMSRequest,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Send a test SMS to verify Twilio configuration"""
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Twilio integration not found")

    if not integration.is_verified:
        raise HTTPException(status_code=400, detail="Twilio integration not verified")

    # Decrypt credentials
    account_sid = decrypt_credential(integration.account_sid)
    auth_token = decrypt_credential(integration.auth_token)

    # Prepare message
    message_body = (
        f"Test message from CleanEnroll! Your SMS notifications are working correctly. 🎉"
    )

    try:
        # Determine from number
        from_number = None
        if integration.messaging_service_sid:
            messaging_service_sid = decrypt_credential(integration.messaging_service_sid)
        else:
            from_number = integration.phone_number

        # Send SMS via Twilio API
        async with httpx.AsyncClient() as client:
            data = {
                "To": request.phone_number,
                "Body": message_body,
            }

            if integration.messaging_service_sid:
                data["MessagingServiceSid"] = messaging_service_sid
            else:
                data["From"] = from_number

            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data=data,
                timeout=10.0,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                message_sid = result.get("sid")

                # Log the SMS
                sms_log = TwilioSMSLog(
                    user_id=current_user.id,
                    integration_id=integration.id,
                    to_phone=request.phone_number,
                    message_body=message_body,
                    message_type="test",
                    twilio_message_sid=message_sid,
                    status="sent",
                )
                db.add(sms_log)

                # Update last test time
                integration.last_test_at = datetime.utcnow()
                db.commit()

                logger.info(f"Test SMS sent successfully for user {current_user.id}")

                return {
                    "message": "Test SMS sent successfully",
                    "message_sid": message_sid,
                    "status": result.get("status"),
                }
            else:
                error_data = response.json()
                error_message = error_data.get("message", "Unknown error")

                # Log failed SMS
                sms_log = TwilioSMSLog(
                    user_id=current_user.id,
                    integration_id=integration.id,
                    to_phone=request.phone_number,
                    message_body=message_body,
                    message_type="test",
                    status="failed",
                    error_message=error_message,
                )
                db.add(sms_log)
                db.commit()

                raise HTTPException(status_code=400, detail=f"Failed to send SMS: {error_message}")

    except httpx.HTTPError as e:
        logger.error(f"Twilio API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Twilio API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error sending test SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending SMS: {str(e)}")


@router.get("/logs")
async def get_sms_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """Get SMS activity logs"""
    integration = (
        db.query(TwilioIntegration).filter(TwilioIntegration.user_id == current_user.id).first()
    )

    if not integration:
        return {"logs": []}

    logs = (
        db.query(TwilioSMSLog)
        .filter(TwilioSMSLog.integration_id == integration.id)
        .order_by(TwilioSMSLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "logs": [
            {
                "id": log.id,
                "to_phone": log.to_phone,
                "message_type": log.message_type,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }
