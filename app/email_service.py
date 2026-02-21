"""
Unified Email Service using Resend (fallback) or Custom SMTP
Provides email functionality using MJML templates for responsive design
"""

import io
import logging
import smtplib
import ssl
import zipfile
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union

import aiohttp
import resend
from mjml import mjml_to_html

from .config import EMAIL_FROM_ADDRESS, RESEND_API_KEY, SMTP_ENCRYPTION_KEY
from .email_templates import (
    THEME,
    client_signature_confirmation_template,
    contract_fully_executed_template,
    contract_fully_executed_schedule_invitation_template,
    contract_signed_notification_template,
    email_verification_template,
    form_submission_confirmation_template,
    invoice_ready_template,
    new_client_notification_template,
    new_schedule_request_template,
    password_reset_template,
    payment_confirmation_client_template,
    payment_received_notification_template,
    quote_approved_template,
    quote_review_notification_template,
    quote_submitted_confirmation_template,
    schedule_confirmed_provider_template,
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
        # mjml_to_html returns a dict with 'html' and 'errors' keys
        if isinstance(result, dict):
            if result.get("errors"):
                logger.warning(f"MJML compilation warnings: {result['errors']}")
            return result.get("html", "")
        # If it returns a string directly (older versions)
        return str(result)
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


async def send_schedule_invitation_after_signing(
    to: str,
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_id: str,
    client_public_id: str,
) -> dict:
    """Send email to client inviting them to schedule after both parties sign the MSA"""
    mjml_content = contract_fully_executed_schedule_invitation_template(
        client_name=client_name,
        business_name=business_name,
        contract_title=contract_title,
        contract_id=contract_id,
        client_public_id=client_public_id,
    )

    return await send_email(
        to=to,
        subject=f"Schedule Your First Cleaning - {business_name}",
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


async def send_provider_contract_signed_confirmation(
    to: str,
    provider_name: str,
    contract_id: str,
    client_name: str,
    property_address: Optional[str] = None,
    contract_pdf_url: Optional[str] = None,
) -> dict:
    """Send provider-only confirmation after they sign a contract"""
    from .email_templates import get_base_template

    content_sections = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      Contract <strong>{contract_id}</strong> for {client_name}{f' ({property_address})' if property_address else ''} is fully executed. Client has been notified.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0">
      Contract ID: {contract_id}<br/>
      Client: {client_name}
      {f'<br/>Property: {property_address}' if property_address else ''}
    </mj-text>
    
    <mj-text color="{THEME['success']}" font-size="14px" font-weight="700" padding="20px 0 0 0">
      ✓ Schedule confirmed - Ready to start service
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px">
      The client's proposed schedule has been reviewed and confirmed. Signed PDF attached.
    </mj-text>
    """

    mjml_content = get_base_template(
        title="Contract Signed Successfully",
        preview_text="You've Signed Contract - Client Notification Sent",
        content_sections=content_sections,
        cta_url=contract_pdf_url,
        cta_label="View Signed Contract" if contract_pdf_url else None,
        is_user_email=True,
    )

    return await send_email(
        to=to,
        subject="You've Signed Contract - Client Notification Sent",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_scheduling_proposal_email(
    client_email: str,
    client_name: str,
    provider_name: str,
    contract_id: str,
    time_slots: list[dict],
    expires_at: str,
) -> dict:
    """Send scheduling proposal with time slots to client"""
    from .email_templates import get_base_template

    # Format time slots for display
    slots_html = ""
    for i, slot in enumerate(time_slots[:3], 1):
        slots_html += f"""
        <mj-text font-size="15px" color="{THEME['text_primary']}" padding="8px 0">
          <strong>Option {i}:</strong> {slot.get('date', 'N/A')} at {slot.get('start_time', 'N/A')}
        </mj-text>
        """

    schedule_url = f"https://app.cleanenroll.com/schedule-selection/{contract_id}"

    content_sections = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      <strong>{provider_name}</strong> has proposed the following time slots for your cleaning service:
    </mj-text>
    
    {slots_html}
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="20px 0">
      Please select your preferred time slot or propose an alternative. This proposal expires on {expires_at}.
    </mj-text>
    """

    mjml_content = get_base_template(
        title="Choose Your Cleaning Time",
        preview_text=f"Scheduling Proposal from {provider_name}",
        content_sections=content_sections,
        cta_url=schedule_url,
        cta_label="Select Time Slot",
    )

    return await send_email(
        to=client_email,
        subject=f"Choose Your Cleaning Time - {provider_name}",
        mjml_content=mjml_content,
    )


async def send_scheduling_accepted_email(
    provider_email: str,
    provider_name: str,
    client_name: str,
    contract_id: str,
    selected_date: str,
    start_time: str,
    end_time: str,
    property_address: Optional[str] = None,
) -> dict:
    """Notify provider when client accepts a proposed time slot"""
    mjml_content = schedule_confirmed_provider_template(
        provider_name=provider_name,
        client_name=client_name,
        scheduled_date=selected_date,
        scheduled_time=f"{start_time} - {end_time}",
    )

    return await send_email(
        to=provider_email,
        subject=f"Schedule Confirmed: {client_name} - {selected_date}",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_appointment_confirmed_to_client(
    client_email: str,
    client_name: str,
    provider_name: str,
    confirmed_date: str,
    confirmed_start_time: str,
    confirmed_end_time: str,
) -> dict:
    """Send appointment confirmation email to client"""
    from .email_templates import schedule_confirmed_client_template

    scheduled_time = f"{confirmed_start_time} - {confirmed_end_time}"
    mjml_content = schedule_confirmed_client_template(
        client_name=client_name,
        business_name=provider_name,
        scheduled_date=confirmed_date,
        scheduled_time=scheduled_time,
    )

    return await send_email(
        to=client_email,
        subject=f"Your Cleaning is Scheduled! - {provider_name}",
        mjml_content=mjml_content,
        is_user_email=False,
    )


async def send_schedule_accepted_confirmation_to_provider(
    provider_email: str,
    provider_name: str,
    client_name: str,
    confirmed_date: str,
    confirmed_start_time: str,
    confirmed_end_time: str,
    client_address: Optional[str] = None,
) -> dict:
    """Send schedule confirmation email to provider"""
    from .email_templates import schedule_confirmed_provider_template

    scheduled_time = f"{confirmed_start_time} - {confirmed_end_time}"
    mjml_content = schedule_confirmed_provider_template(
        provider_name=provider_name,
        client_name=client_name,
        scheduled_date=confirmed_date,
        scheduled_time=scheduled_time,
    )

    return await send_email(
        to=provider_email,
        subject=f"Schedule Confirmed: {client_name} - {confirmed_date}",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_scheduling_counter_proposal_email(
    provider_email: str,
    provider_name: str,
    client_name: str,
    contract_id: str,
    preferred_days: str,
    time_window: str,
    client_notes: Optional[str] = None,
) -> dict:
    """Notify provider when client proposes alternative times"""
    from .email_templates import get_base_template

    notes_section = ""
    if client_notes:
        notes_section = f"""
        <mj-text font-size="14px" color="{THEME['text_muted']}" padding="16px 0 0 0">
          <strong>Client Notes:</strong><br/>
          {client_notes}
        </mj-text>
        """

    content_sections = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      <strong>{client_name}</strong> has proposed alternative times for their cleaning service.
    </mj-text>
    
    <mj-text font-size="15px" color="{THEME['text_primary']}" padding="20px 0 8px 0">
      <strong>Preferred Days:</strong> {preferred_days}
    </mj-text>
    
    <mj-text font-size="15px" color="{THEME['text_primary']}" padding="0">
      <strong>Preferred Time:</strong> {time_window}
    </mj-text>
    
    {notes_section}
    
    <mj-text color="#92400e" font-size="14px" padding="20px 0">
      ⏰ <strong>Action Required:</strong> Please review and propose new time slots in your dashboard.
    </mj-text>
    """

    mjml_content = get_base_template(
        title="Client Proposed Alternative Times",
        preview_text=f"Counter-Proposal from {client_name}",
        content_sections=content_sections,
        cta_url="https://cleanenroll.com/schedule",
        cta_label="Review & Respond",
        is_user_email=True,
    )

    return await send_email(
        to=provider_email,
        subject=f"Counter-Proposal: {client_name} Suggested Alternative Times",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_pending_booking_notification(
    provider_email: str,
    provider_name: str,
    client_name: str,
    scheduled_date: str,
    start_time: str,
    end_time: str,
    property_address: Optional[str] = None,
    schedule_id: Optional[int] = None,
    client_email: Optional[str] = None,
    client_phone: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> dict:
    """Notify provider about pending booking that requires approval"""
    mjml_content = new_schedule_request_template(
        provider_name=provider_name,
        client_name=client_name,
        scheduled_date=scheduled_date,
        scheduled_time=f"{start_time} - {end_time}",
        duration_minutes=duration_minutes or 120,
        client_email=client_email or "",
        client_phone=client_phone or "",
        dashboard_url="https://cleanenroll.com/schedule",
    )

    return await send_email(
        to=provider_email,
        subject=f"New Booking Request: {client_name} - {scheduled_date}",
        mjml_content=mjml_content,
        is_user_email=True,
    )


async def send_invoice_payment_link_email(
    to: str,
    client_name: str,
    business_name: str,
    invoice_number: str,
    invoice_title: str,
    total_amount: float,
    currency: str = "USD",
    due_date: Optional[str] = None,
    payment_link: Optional[str] = None,
    is_recurring: bool = False,
    is_deposit: bool = False,
    deposit_percentage: int = 50,
    remaining_balance: Optional[float] = None,
) -> dict:
    """
    Send invoice with payment link to client

    Args:
        is_deposit: If True, this is a deposit invoice (50% upfront)
        deposit_percentage: Percentage of deposit (default 50)
        remaining_balance: Remaining balance due after job completion
    """
    mjml_content = invoice_ready_template(
        client_name=client_name,
        business_name=business_name,
        invoice_number=invoice_number,
        amount=total_amount,
        due_date=due_date or "",
        payment_url=payment_link or "",
        is_deposit=is_deposit,
        deposit_percentage=deposit_percentage,
        remaining_balance=remaining_balance,
    )

    subject = f"Invoice Ready: {invoice_number} - {business_name}"
    if is_deposit:
        subject = f"Deposit Invoice ({deposit_percentage}%): {invoice_number} - {business_name}"
    elif is_recurring:
        subject = f"Recurring Invoice: {invoice_number} - {business_name}"

    return await send_email(
        to=to,
        subject=subject,
        mjml_content=mjml_content,
    )


async def send_contract_cancelled_email(
    client_email: str,
    client_name: str,
    contract_title: str,
    business_name: str,
    business_config=None,
) -> dict:
    """Send contract cancellation notification to client"""
    from .email_templates import get_base_template

    content_sections = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Your contract with <strong>{business_name}</strong> has been cancelled.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0">
      Contract: {contract_title}<br/>
      Status: Cancelled
    </mj-text>
    
    <mj-text>
      If you have any questions about this cancellation, please contact {business_name} directly.
    </mj-text>
    """

    mjml_content = get_base_template(
        title="Contract Cancelled",
        preview_text=f"Contract Cancelled - {contract_title}",
        content_sections=content_sections,
    )

    return await send_email(
        to=client_email,
        subject=f"Contract Cancelled - {contract_title}",
        mjml_content=mjml_content,
        business_config=business_config,
    )


async def send_payment_thank_you_email(
    client_email: str,
    client_name: str,
    business_name: str,
    invoice_number: str,
    amount: float,
    currency: str = "USD",
) -> dict:
    """Send payment thank you email to client"""
    from datetime import datetime

    payment_date = datetime.utcnow().strftime("%B %d, %Y")

    mjml_content = payment_confirmation_client_template(
        client_name=client_name,
        business_name=business_name,
        amount=amount,
        contract_title=f"Invoice {invoice_number}",
        payment_date=payment_date,
    )

    return await send_email(
        to=client_email,
        subject=f"Payment Received - Thank You! ({invoice_number})",
        mjml_content=mjml_content,
    )
