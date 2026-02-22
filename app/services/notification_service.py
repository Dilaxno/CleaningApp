"""
Unified Notification Service
Handles both email and SMS notifications for all workflow events
Ensures both channels are triggered consistently from the same event source
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from ..shared.validators import validate_us_phone

logger = logging.getLogger(__name__)


async def send_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    notification_type: str,
    email_func,
    sms_func,
    email_kwargs: dict,
    sms_kwargs: dict,
) -> dict:
    """
    Unified notification sender that handles both email and SMS

    Args:
        db: Database session
        user_id: Provider user ID
        client_email: Client email address
        client_phone: Client phone number
        client_name: Client name for logging
        notification_type: Type of notification (for logging)
        email_func: Email function to call
        sms_func: SMS function to call
        email_kwargs: Kwargs for email function
        sms_kwargs: Kwargs for SMS function

    Returns:
        Dict with email_sent and sms_sent status
    """
    result = {"email_sent": False, "sms_sent": False, "email_error": None, "sms_error": None}

    # Send Email
    if client_email:
        try:
            logger.info(f"📧 Sending {notification_type} email to {client_email}")
            await email_func(**email_kwargs)
            result["email_sent"] = True
            logger.info(f"✅ {notification_type} email sent successfully to {client_email}")
        except Exception as e:
            result["email_error"] = str(e)
            logger.error(f"❌ Failed to send {notification_type} email to {client_email}: {e}")
    else:
        logger.debug(f"⚠️ No email address for {notification_type} notification to {client_name}")

    # Send SMS (if Twilio is connected and enabled)
    if client_phone:
        try:
            # Validate and format phone number to E.164
            formatted_phone = validate_us_phone(client_phone)
            if not formatted_phone:
                logger.warning(f"⚠️ Invalid phone number format for {client_name}: {client_phone}")
                result["sms_error"] = "Invalid phone number format"
            else:
                logger.info(f"📱 Attempting to send {notification_type} SMS to {formatted_phone}")
                sms_kwargs["to_phone"] = formatted_phone
                success, error = await sms_func(**sms_kwargs)

                if success:
                    result["sms_sent"] = True
                    logger.info(
                        f"✅ {notification_type} SMS sent successfully to {formatted_phone}"
                    )
                else:
                    result["sms_error"] = error
                    if error and "disabled" not in error.lower():
                        logger.warning(
                            f"⚠️ {notification_type} SMS not sent to {formatted_phone}: {error}"
                        )
                    else:
                        logger.debug(f"ℹ️ {notification_type} SMS skipped: {error}")
        except Exception as e:
            result["sms_error"] = str(e)
            logger.error(f"❌ Failed to send {notification_type} SMS to {client_phone}: {e}")
    else:
        logger.debug(f"⚠️ No phone number for {notification_type} SMS to {client_name}")

    return result


async def send_estimate_approval_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    business_name: str,
    estimate_amount: float,
    client_public_id: str,
) -> dict:
    """Send estimate approval notification via email and SMS"""
    from ..email_service import send_quote_approved_email
    from .twilio_service import send_estimate_approval_sms

    return await send_notification(
        db=db,
        user_id=user_id,
        client_email=client_email,
        client_phone=client_phone,
        client_name=client_name,
        notification_type="estimate_approval",
        email_func=send_quote_approved_email,
        sms_func=send_estimate_approval_sms,
        email_kwargs={
            "to": client_email,
            "client_name": client_name,
            "business_name": business_name,
            "final_quote_amount": estimate_amount,
            "was_adjusted": False,
            "adjustment_notes": None,
            "client_public_id": client_public_id,
        },
        sms_kwargs={
            "db": db,
            "user_id": user_id,
            "client_name": client_name,
            "estimate_amount": estimate_amount,
        },
    )


async def send_schedule_confirmation_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    business_name: str,
    schedule_date: str,
    schedule_time: str,
) -> dict:
    """Send schedule confirmation notification via email and SMS"""
    from ..email_service import send_appointment_confirmed_to_client
    from .twilio_service import send_schedule_confirmation_sms

    # Parse schedule_time if it contains a range (e.g., "10:00 AM - 12:00 PM")
    start_time = schedule_time.split("-")[0].strip() if "-" in schedule_time else schedule_time
    end_time = schedule_time.split("-")[1].strip() if "-" in schedule_time else ""

    return await send_notification(
        db=db,
        user_id=user_id,
        client_email=client_email,
        client_phone=client_phone,
        client_name=client_name,
        notification_type="schedule_confirmation",
        email_func=send_appointment_confirmed_to_client,
        sms_func=send_schedule_confirmation_sms,
        email_kwargs={
            "client_email": client_email,
            "client_name": client_name,
            "provider_name": business_name,
            "confirmed_date": schedule_date,
            "confirmed_start_time": start_time,
            "confirmed_end_time": end_time,
        },
        sms_kwargs={
            "db": db,
            "user_id": user_id,
            "client_name": client_name,
            "schedule_date": schedule_date,
            "schedule_time": schedule_time,
        },
    )


async def send_contract_signed_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_id: int,
    contract_pdf_url: Optional[str] = None,
) -> dict:
    """Send contract signed notification via email and SMS"""
    from ..email_service import send_client_signature_confirmation
    from .twilio_service import send_contract_signed_sms

    return await send_notification(
        db=db,
        user_id=user_id,
        client_email=client_email,
        client_phone=client_phone,
        client_name=client_name,
        notification_type="contract_signed",
        email_func=send_client_signature_confirmation,
        sms_func=send_contract_signed_sms,
        email_kwargs={
            "to": client_email,
            "client_name": client_name,
            "business_name": business_name,
            "contract_title": contract_title,
            "contract_pdf_url": contract_pdf_url,
        },
        sms_kwargs={
            "db": db,
            "user_id": user_id,
            "client_name": client_name,
            "contract_id": contract_id,
        },
    )


async def send_payment_confirmation_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    business_name: str,
    invoice_number: str,
    amount: float,
    currency: str = "USD",
) -> dict:
    """Send payment confirmation notification via email and SMS"""
    from ..email_service import send_payment_thank_you_email
    from .twilio_service import send_payment_confirmation_sms

    return await send_notification(
        db=db,
        user_id=user_id,
        client_email=client_email,
        client_phone=client_phone,
        client_name=client_name,
        notification_type="payment_confirmation",
        email_func=send_payment_thank_you_email,
        sms_func=send_payment_confirmation_sms,
        email_kwargs={
            "client_email": client_email,
            "client_name": client_name,
            "business_name": business_name,
            "invoice_number": invoice_number,
            "amount": amount,
            "currency": currency,
        },
        sms_kwargs={
            "db": db,
            "user_id": user_id,
            "client_name": client_name,
            "amount": amount,
            "invoice_number": invoice_number,
        },
    )


async def send_contract_fully_executed_notification(
    db: Session,
    user_id: int,
    client_email: Optional[str],
    client_phone: Optional[str],
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_id: str,
    service_type: str,
    start_date: Optional[str] = None,
    total_value: Optional[float] = None,
    property_address: Optional[str] = None,
    business_phone: Optional[str] = None,
    contract_pdf_url: Optional[str] = None,
    scheduled_time_confirmed: bool = False,
    scheduled_start_time: Optional[str] = None,
    contract_numeric_id: Optional[int] = None,
) -> dict:
    """Send contract fully executed notification via email and SMS"""
    from ..email_service import send_contract_fully_executed_email
    from .twilio_service import send_contract_signed_sms

    return await send_notification(
        db=db,
        user_id=user_id,
        client_email=client_email,
        client_phone=client_phone,
        client_name=client_name,
        notification_type="contract_fully_executed",
        email_func=send_contract_fully_executed_email,
        sms_func=send_contract_signed_sms,
        email_kwargs={
            "to": client_email,
            "client_name": client_name,
            "business_name": business_name,
            "contract_title": contract_title,
            "contract_id": contract_id,
            "service_type": service_type,
            "start_date": start_date,
            "total_value": total_value,
            "property_address": property_address,
            "business_phone": business_phone,
            "contract_pdf_url": contract_pdf_url,
            "scheduled_time_confirmed": scheduled_time_confirmed,
            "scheduled_start_time": scheduled_start_time,
        },
        sms_kwargs={
            "db": db,
            "user_id": user_id,
            "client_name": client_name,
            "contract_id": contract_numeric_id if contract_numeric_id else 0,
        },
    )
