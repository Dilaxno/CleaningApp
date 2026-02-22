"""
Twilio SMS Service
Handles sending SMS notifications for various workflow events
"""

import logging
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from ..config import SECRET_KEY
from ..models_twilio import TwilioIntegration, TwilioSMSLog

logger = logging.getLogger(__name__)

# Encryption for credentials
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))


def decrypt_credential(encrypted_credential: str) -> str:
    """Decrypt a stored credential"""
    return cipher_suite.decrypt(encrypted_credential.encode()).decode()


async def send_sms(
    db: Session,
    user_id: int,
    to_phone: str,
    message_body: str,
    message_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send SMS via Twilio

    Args:
        db: Database session
        user_id: User ID
        to_phone: Recipient phone number (should be in E.164 format)
        message_body: SMS message content
        message_type: Type of message (estimate_approval, schedule_confirmation, etc.)
        entity_type: Optional entity type (Contract, Schedule, etc.)
        entity_id: Optional entity ID

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    # Validate phone number format
    if not to_phone:
        logger.debug(f"No phone number provided for user {user_id}")
        return False, "No phone number provided"

    # Ensure phone number is in E.164 format
    if not to_phone.startswith("+"):
        logger.warning(f"Phone number not in E.164 format: {to_phone}")
        return False, "Phone number must be in E.164 format (e.g., +1234567890)"

    # Get integration
    integration = db.query(TwilioIntegration).filter(TwilioIntegration.user_id == user_id).first()

    if not integration:
        logger.debug(f"No Twilio integration found for user {user_id}")
        return False, "No Twilio integration"

    if not integration.sms_enabled:
        logger.debug(f"SMS disabled for user {user_id}")
        return False, "SMS disabled"

    if not integration.is_verified:
        logger.warning(f"Twilio integration not verified for user {user_id}")
        return False, "Integration not verified"

    # Check if this message type is enabled
    message_type_settings = {
        "estimate_approval": integration.send_estimate_approval,
        "schedule_confirmation": integration.send_schedule_confirmation,
        "contract_signed": integration.send_contract_signed,
        "job_reminder": integration.send_job_reminder,
        "job_completion": integration.send_job_completion,
        "payment_confirmation": integration.send_payment_confirmation,
    }

    if message_type in message_type_settings and not message_type_settings[message_type]:
        logger.debug(f"Message type {message_type} disabled for user {user_id}")
        return False, f"Message type {message_type} disabled"

    # Decrypt credentials
    try:
        account_sid = decrypt_credential(integration.account_sid)
        auth_token = decrypt_credential(integration.auth_token)
    except Exception as e:
        logger.error(f"Failed to decrypt Twilio credentials: {str(e)}")
        return False, "Failed to decrypt credentials"

    # Prepare message data
    try:
        logger.info(f"📱 Preparing SMS: type={message_type}, to={to_phone}, user={user_id}")

        data = {
            "To": to_phone,
            "Body": message_body,
        }

        if integration.messaging_service_sid:
            messaging_service_sid = decrypt_credential(integration.messaging_service_sid)
            data["MessagingServiceSid"] = messaging_service_sid
            logger.debug(f"Using Messaging Service SID for user {user_id}")
        else:
            data["From"] = integration.phone_number
            logger.debug(f"Using From number: {integration.phone_number}")

        # Send SMS via Twilio API
        logger.info(f"🚀 Sending SMS to Twilio API for {to_phone}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data=data,
                timeout=10.0,
            )

            logger.info(f"📡 Twilio API response status: {response.status_code}")

            if response.status_code in [200, 201]:
                result = response.json()
                message_sid = result.get("sid")

                # Log successful SMS
                sms_log = TwilioSMSLog(
                    user_id=user_id,
                    integration_id=integration.id,
                    to_phone=to_phone,
                    message_body=message_body,
                    message_type=message_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    twilio_message_sid=message_sid,
                    status="sent",
                )
                db.add(sms_log)
                db.commit()

                logger.info(
                    f"✅ SMS sent successfully: {message_type} to {to_phone} (SID: {message_sid})"
                )
                return True, None
            else:
                error_data = response.json()
                error_message = error_data.get("message", "Unknown error")
                error_code = error_data.get("code")

                # Log failed SMS
                sms_log = TwilioSMSLog(
                    user_id=user_id,
                    integration_id=integration.id,
                    to_phone=to_phone,
                    message_body=message_body,
                    message_type=message_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status="failed",
                    error_message=(
                        f"[{error_code}] {error_message}" if error_code else error_message
                    ),
                )
                db.add(sms_log)
                db.commit()

                logger.error(f"❌ Twilio API error [{error_code}]: {error_message}")
                return False, error_message

    except httpx.HTTPError as e:
        logger.error(f"Twilio API error: {str(e)}")
        # Log failed SMS
        sms_log = TwilioSMSLog(
            user_id=user_id,
            integration_id=integration.id,
            to_phone=to_phone,
            message_body=message_body,
            message_type=message_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status="failed",
            error_message=str(e),
        )
        db.add(sms_log)
        db.commit()
        return False, str(e)
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        return False, str(e)


# SMS Template Functions
async def send_estimate_approval_sms(
    db: Session, user_id: int, client_phone: str, client_name: str, estimate_amount: float
):
    """Send SMS when estimate is approved"""
    message = (
        f"Hi {client_name}! Your estimate for ${estimate_amount:.2f} has been approved. "
        f"We'll be in touch soon to schedule your service. - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="estimate_approval",
    )


async def send_schedule_confirmation_sms(
    db: Session,
    user_id: int,
    client_phone: str,
    client_name: str,
    schedule_date: str,
    schedule_time: str,
):
    """Send SMS when schedule is confirmed"""
    message = (
        f"Hi {client_name}! Your cleaning is confirmed for {schedule_date} at {schedule_time}. "
        f"We look forward to serving you! - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="schedule_confirmation",
    )


async def send_contract_signed_sms(
    db: Session, user_id: int, client_phone: str, client_name: str, contract_id: int
):
    """Send SMS when contract is signed"""
    message = (
        f"Hi {client_name}! Your Master Service Agreement has been signed. "
        f"Thank you for choosing us! - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="contract_signed",
        entity_type="Contract",
        entity_id=contract_id,
    )


async def send_job_reminder_sms(
    db: Session,
    user_id: int,
    client_phone: str,
    client_name: str,
    job_date: str,
    hours_until: int,
):
    """Send SMS reminder before job"""
    message = (
        f"Hi {client_name}! Reminder: Your cleaning is scheduled for {job_date} "
        f"(in {hours_until} hours). See you soon! - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="job_reminder",
    )


async def send_job_completion_sms(db: Session, user_id: int, client_phone: str, client_name: str):
    """Send SMS after job completion"""
    message = (
        f"Hi {client_name}! Your cleaning is complete. "
        f"We hope you're satisfied with our service! - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="job_completion",
    )


async def send_payment_confirmation_sms(
    db: Session,
    user_id: int,
    client_phone: str,
    client_name: str,
    amount: float,
    invoice_number: str,
):
    """Send SMS when payment is received"""
    message = (
        f"Hi {client_name}! Payment of ${amount:.2f} received for invoice #{invoice_number}. "
        f"Thank you! - CleanEnroll"
    )
    return await send_sms(
        db=db,
        user_id=user_id,
        to_phone=client_phone,
        message_body=message,
        message_type="payment_confirmation",
    )
