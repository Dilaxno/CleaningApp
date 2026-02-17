"""
Unified Email Service using Resend (fallback) or Custom SMTP
Provides email functionality using MJML templates for responsive design
"""

import io
import logging
import os
import smtplib
import ssl
import zipfile
from datetime import date, datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union

import aiohttp
import resend
from mjml import mjml_to_html

from .config import EMAIL_FROM_ADDRESS, FRONTEND_URL, RESEND_API_KEY, SMTP_ENCRYPTION_KEY
from .email_templates import (
    client_signature_confirmation_template,
    contract_fully_executed_template,
    contract_signed_notification_template,
    email_verification_template,
    form_submission_confirmation_template,
    new_client_notification_template,
    password_reset_template,
    payment_received_notification_template,
    quote_approved_template,
    quote_review_notification_template,
    quote_submitted_confirmation_template,
    welcome_email_template,
)

logger = logging.getLogger(__name__)

# Initialize Resend as fallback
resend.api_key = RESEND_API_KEY

# Initialize encryption for SMTP passwords
try:
    from cryptography.fernet import Fernet

    fernet = Fernet(SMTP_ENCRYPTION_KEY) if SMTP_ENCRYPTION_KEY else None
except Exception:
    fernet = None


def decrypt_password(encrypted: str) -> str:
    """Decrypt SMTP password"""
    if not fernet or not encrypted:
        return encrypted or ""
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


def get_sender_email(business_config=None, business_name: str = "CleanEnroll") -> str:
    """
    Get the appropriate sender email address.
    Priority order:
    1. Verified subdomain email (e.g., bookings@mail.preclean.com)
    2. Custom SMTP email if configured and live
    3. CleanEnroll default address
    """
    if (
        business_config
        and business_config.subdomain_verification_status == "verified"
        and business_config.email_subdomain
    ):
        subdomain_email = f"bookings@{business_config.email_subdomain}"
        return f"{business_name} <{subdomain_email}>"

    if business_config and business_config.smtp_status == "live" and business_config.smtp_email:
        return f"{business_name} <{business_config.smtp_email}>"

    return EMAIL_FROM_ADDRESS


def send_via_custom_smtp(
    business_config,
    to: Union[str, list[str]],
    subject: str,
    html_content: str,
    from_address: str,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """Send email via user's custom SMTP server"""
    try:
        host = business_config.smtp_host
        port = business_config.smtp_port or 587
        username = business_config.smtp_username
        password = decrypt_password(business_config.smtp_password)
        use_tls = business_config.smtp_use_tls if business_config.smtp_use_tls is not None else True

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = to if isinstance(to, str) else ", ".join(to)

        msg.attach(MIMEText(html_content, "html"))

        if attachments:
            for attachment in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment["content"])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)

        recipients = [to] if isinstance(to, str) else to

        if port == 465:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)

        server.login(username, password)
        server.sendmail(from_address.split("<")[-1].rstrip(">"), recipients, msg.as_string())
        server.quit()

        logger.info(f"✅ Custom SMTP email sent successfully via {business_config.smtp_host}")
        return {"id": f"smtp-{datetime.utcnow().timestamp()}", "success": True}

    except Exception as e:
        logger.error(f"❌ Custom SMTP send failed: {e}")
        raise Exception(f"Custom SMTP failed: {str(e)}") from e


async def create_property_shots_zip(
    property_shots_keys: list[str], client_name: str
) -> Optional[bytes]:
    """Create a zip file containing property shots from R2 storage"""
    if not property_shots_keys:
        return None

    try:
        from .routes.upload import generate_presigned_url

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i, key in enumerate(property_shots_keys[:12]):
                try:
                    presigned_url = generate_presigned_url(key, expiration=3600)

                    async with aiohttp.ClientSession() as session:
                        async with session.get(presigned_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                file_ext = key.split(".")[-1] if "." in key else "jpg"
                                filename = f"property_shot_{i+1:02d}.{file_ext}"
                                zip_file.writestr(filename, image_data)
                            else:
                                logger.warning(
                                    f"Failed to download property shot {key}: HTTP {response.status}"
                                )
                except Exception as e:
                    logger.warning(f"Failed to process property shot {key}: {e}")
                    continue

        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        if len(zip_data) > 0:
            logger.info(
                f"Created property shots zip with {len(property_shots_keys)} images for {client_name}"
            )
            return zip_data
        else:
            logger.warning("Property shots zip is empty")
            return None

    except Exception as e:
        logger.error(f"Failed to create property shots zip: {e}")
        return None


def compile_mjml_to_html(mjml_content: str) -> str:
    """Compile MJML template to production-ready HTML"""
    try:
        result = mjml_to_html(mjml_content)
        return result
    except Exception as e:
        logger.error(f"MJML compilation error: {e}")
        raise Exception(f"Failed to compile MJML template: {str(e)}") from e


async def send_email(
    to: Union[str, list[str]],
    subject: str,
    mjml_content: str,
    from_address: Optional[str] = None,
    business_config=None,
    is_user_email: bool = False,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """
    Send an email using custom SMTP (if configured) or Resend (fallback)

    Args:
        to: Recipient email(s)
        subject: Email subject line
        mjml_content: MJML template content (will be compiled to HTML)
        from_address: Optional custom from address
        business_config: Optional BusinessConfig for custom SMTP
        is_user_email: Whether this email is to a CleanEnroll user (not a client)
        attachments: Optional list of attachments

    Returns:
        Send response dict
    """
    html_content = compile_mjml_to_html(mjml_content)

    recipients = [to] if isinstance(to, str) else to
    sender = from_address or EMAIL_FROM_ADDRESS

    if business_config and business_config.smtp_status == "live" and business_config.smtp_host:
        try:
            logger.info(f"📧 Sending email via custom SMTP: {business_config.smtp_host}")
            response = send_via_custom_smtp(
                business_config=business_config,
                to=recipients,
                subject=subject,
                html_content=html_content,
                from_address=sender,
                attachments=attachments,
            )
            return response
        except Exception as e:
            logger.warning(f"⚠️ Custom SMTP failed, falling back to Resend: {e}")

    if not RESEND_API_KEY:
        logger.error("❌ No email service configured - RESEND_API_KEY missing and no custom SMTP")
        raise Exception("Email service not configured")

    try:
        logger.info(f"📧 Sending email via Resend to: {to}")
        email_data = {
            "from": sender,
            "to": recipients,
            "subject": subject,
            "html": html_content,
        }

        if attachments:
            email_data["attachments"] = [
                {"filename": attachment["filename"], "content": attachment["content"]}
                for attachment in attachments
            ]

        response = resend.Emails.send(email_data)
        logger.info(f"✅ Email sent successfully via Resend: {response}")
        return response
    except Exception as e:
        logger.error(f"❌ Email send error to {recipients}: {e}")
        raise Exception(f"Failed to send email: {str(e)}") from e


# ============================================
# Pre-built Email Templates for Common Events
# All templates use MJML for responsive design
# ============================================


async def send_welcome_email(to: str, user_name: str) -> dict:
    """Send welcome email to new users"""
    mjml_content = welcome_email_template(user_name)
    return await send_email(
        to=to,
        subject="Welcome to CleanEnroll",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_email_verification_otp(to: str, user_name: str, otp: str) -> dict:
    """Send OTP for email verification"""
    mjml_content = email_verification_template(user_name, otp)
    return await send_email(
        to=to,
        subject="Verify Your Email - CleanEnroll",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_password_reset_email(to: str, reset_link: str) -> dict:
    """Send password reset email"""
    mjml_content = password_reset_template(reset_link)
    return await send_email(
        to=to,
        subject="Reset Your Password - CleanEnroll",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_new_client_notification(
    to: str,
    business_name: str,
    client_name: str,
    client_email: str,
    property_type: str,
    property_shots_keys: Optional[list[str]] = None,
) -> dict:
    """Notify business owner of new client submission"""
    attachments = None
    property_shots_count = 0

    if property_shots_keys and len(property_shots_keys) > 0:
        property_shots_count = len(property_shots_keys)
        try:
            zip_data = await create_property_shots_zip(property_shots_keys, client_name)
            if zip_data:
                safe_client_name = "".join(
                    c for c in client_name if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()
                filename = f"property_shots_{safe_client_name.replace(' ', '_')}.zip"

                attachments = [
                    {"filename": filename, "content": zip_data, "content_type": "application/zip"}
                ]
        except Exception as e:
            logger.warning(f"Failed to create property shots zip for {client_name}: {e}")

    mjml_content = new_client_notification_template(
        business_name=business_name,
        client_name=client_name,
        client_email=client_email,
        property_type=property_type,
        property_shots_count=property_shots_count,
    )

    return await send_email(
        to=to,
        subject=f"New {property_type} Property Intake: {client_name} Ready to Review",
        mjml_content=mjml_content,
        is_user_email=True,
        attachments=attachments,
    )


async def send_form_submission_confirmation(
    to: str,
    client_name: str,
    business_name: str,
    property_type: str = "Property",
) -> dict:
    """Send confirmation to client after form submission"""
    mjml_content = form_submission_confirmation_template(
        client_name=client_name,
        business_name=business_name,
        property_type=property_type,
    )

    return await send_email(
        to=to,
        subject=f"Thank You for Your {property_type} Cleaning Intake, {client_name}",
        mjml_content=mjml_content,
    )


async def send_contract_signed_notification(
    to: str,
    business_name: str,
    client_name: str,
    contract_title: str,
) -> dict:
    """Notify business owner when a client signs their contract"""
    mjml_content = contract_signed_notification_template(
        business_name=business_name,
        client_name=client_name,
        contract_title=contract_title,
    )

    return await send_email(
        to=to,
        subject=f"Contract Signed by {client_name} - Review Schedule & Sign",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_client_signature_confirmation(
    to: str,
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_pdf_url: Optional[str] = None,
) -> dict:
    """Notify client after they sign the contract (awaiting provider signature)"""
    mjml_content = client_signature_confirmation_template(
        client_name=client_name,
        business_name=business_name,
        contract_title=contract_title,
        contract_pdf_url=contract_pdf_url,
    )

    return await send_email(
        to=to,
        subject=f"Contract Signed - Awaiting {business_name}",
        mjml_content=mjml_content,
        is_user_email=False,
    )


async def send_contract_fully_executed_email(
    to: str,
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
) -> dict:
    """Notify client when contract is fully signed by both parties"""
    mjml_content = contract_fully_executed_template(
        client_name=client_name,
        business_name=business_name,
        contract_title=contract_title,
        contract_id=contract_id,
        service_type=service_type,
        start_date=start_date,
        total_value=total_value,
        property_address=property_address,
        business_phone=business_phone,
        contract_pdf_url=contract_pdf_url,
        scheduled_time_confirmed=scheduled_time_confirmed,
        scheduled_start_time=scheduled_start_time,
    )

    return await send_email(
        to=to,
        subject=f"Great News! Your Cleaning Contract is Fully Signed & Ready [Contract {contract_id}]",
        mjml_content=mjml_content,
    )


async def send_quote_submitted_confirmation(
    to: str,
    client_name: str,
    business_name: str,
    quote_amount: float,
) -> dict:
    """Send confirmation email to client after they approve the automated quote"""
    mjml_content = quote_submitted_confirmation_template(
        client_name=client_name,
        business_name=business_name,
        quote_amount=quote_amount,
    )

    return await send_email(
        to=to,
        subject=f"Your Quote Request Has Been Submitted - {business_name}",
        mjml_content=mjml_content,
    )


async def send_quote_review_notification(
    to: str,
    provider_name: str,
    client_name: str,
    client_email: str,
    quote_amount: float,
    client_id: int,
    client_public_id: str,
) -> dict:
    """Send notification email to provider when client approves a quote"""
    mjml_content = quote_review_notification_template(
        provider_name=provider_name,
        client_name=client_name,
        client_email=client_email,
        quote_amount=quote_amount,
        client_public_id=client_public_id,
    )

    return await send_email(
        to=to,
        subject=f"New Quote Approval Request from {client_name}",
        mjml_content=mjml_content,
    )


async def send_quote_approved_email(
    to: str,
    client_name: str,
    business_name: str,
    final_quote_amount: float,
    was_adjusted: bool,
    adjustment_notes: str = None,
    client_public_id: str = None,
) -> dict:
    """Send email to client when provider approves their quote"""
    mjml_content = quote_approved_template(
        client_name=client_name,
        business_name=business_name,
        final_quote_amount=final_quote_amount,
        was_adjusted=was_adjusted,
        adjustment_notes=adjustment_notes,
        client_public_id=client_public_id,
    )

    subject = "Your Quote Has Been Updated" if was_adjusted else "Your Quote Has Been Approved"

    return await send_email(
        to=to,
        subject=f"{subject} - {business_name}",
        mjml_content=mjml_content,
    )


async def send_payment_received_notification(
    provider_email: str,
    provider_name: str,
    client_name: str,
    invoice_number: str,
    amount: float,
    currency: str = "USD",
    payment_date: Optional[str] = None,
) -> dict:
    """Notify provider when client payment is received"""
    mjml_content = payment_received_notification_template(
        provider_name=provider_name,
        client_name=client_name,
        invoice_number=invoice_number,
        amount=amount,
        currency=currency,
        payment_date=payment_date,
    )

    return await send_email(
        to=provider_email,
        subject=f"Payment Received: ${amount:,.2f} from {client_name}",
        mjml_content=mjml_content,
        is_user_email=True,
    )
