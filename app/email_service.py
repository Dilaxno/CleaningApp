"""
Unified Email Service using Resend (fallback) or Custom SMTP
Provides a consistent email template for all automated emails
"""

import io
import logging
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
from jinja2 import Template

from .config import EMAIL_FROM_ADDRESS, FRONTEND_URL, RESEND_API_KEY, SMTP_ENCRYPTION_KEY

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

 Args:
 business_config: BusinessConfig object with smtp and subdomain settings
 business_name: Business name for the sender display name

 Returns:
 Formatted sender email string
 """
 # Check if verified subdomain is available
 if (
 business_config
 and business_config.subdomain_verification_status == "verified"
 and business_config.email_subdomain
 ):
 # Use subdomain for email address (e.g., bookings@mail.preclean.com)
 subdomain_email = f"bookings@{business_config.email_subdomain}"
 return f"{business_name} <{subdomain_email}>"

 # Check if custom SMTP is configured and live
 if business_config and business_config.smtp_status == "live" and business_config.smtp_email:
 return f"{business_name} <{business_config.smtp_email}>"

 # Fallback to default CleanEnroll address
 return EMAIL_FROM_ADDRESS


def send_via_custom_smtp(
 business_config,
 to: Union[str, list[str]],
 subject: str,
 html_content: str,
 from_address: str,
 attachments: Optional[list[dict]] = None,
) -> dict:
 """
 Send email via user's custom SMTP server.
 Returns dict with success status.
 """
 try:
 host = business_config.smtp_host
 port = business_config.smtp_port or 587
 username = business_config.smtp_username
 password = decrypt_password(business_config.smtp_password)
 use_tls = business_config.smtp_use_tls if business_config.smtp_use_tls is not None else True

 # Create message
 msg = MIMEMultipart("mixed")
 msg["Subject"] = subject
 msg["From"] = from_address
 msg["To"] = to if isinstance(to, str) else ", ".join(to)

 # Add HTML content
 msg.attach(MIMEText(html_content, "html"))

 # Add attachments if provided
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

 # Connect and send
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

 logger.info(f" Custom SMTP email sent successfully via {business_config.smtp_host}")
 return {"id": f"smtp-{datetime.utcnow().timestamp()}", "success": True}

 except Exception as e:
 logger.error(f"❌ Custom SMTP send failed: {e}")
 raise Exception(f"Custom SMTP failed: {str(e)}") from e


async def create_property_shots_zip(
 property_shots_keys: list[str], client_name: str
) -> Optional[bytes]:
 """
 Create a zip file containing property shots from R2 storage.

 Args:
 property_shots_keys: List of R2 object keys for property shots
 client_name: Client name for file naming

 Returns:
 Zip file bytes or None if no images or error
 """
 if not property_shots_keys:
 return None

 try:
 from .routes.upload import generate_presigned_url

 zip_buffer = io.BytesIO()

 with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
 for i, key in enumerate(property_shots_keys[:12]): # Limit to 12 images
 try:
 # Generate presigned URL
 presigned_url = generate_presigned_url(key, expiration=3600)

 # Download image
 async with aiohttp.ClientSession() as session:
 async with session.get(presigned_url) as response:
 if response.status == 200:
 image_data = await response.read()

 # Extract file extension from key
 file_ext = key.split(".")[-1] if "." in key else "jpg"
 filename = f"property_shot_{i+1:02d}.{file_ext}"

 # Add to zip
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


# App theme colors - Clean, professional palette
THEME = {
 "primary": "#14b8a6", # Teal - primary brand color
 "primary_dark": "#0d9488", # Darker teal for hover
 "primary_light": "#ccfbf1", # Light teal background
 "background": "#f8fafc", # Soft gray background
 "card_bg": "#ffffff", # White card background
 "text_primary": "#0f172a", # Rich dark text (slate-900)
 "text_secondary": "#475569", # Secondary text (slate-600)
 "text_muted": "#64748b", # Muted gray text (slate-500)
 "border": "#e2e8f0", # Light border (slate-200)
 "border_dark": "#cbd5e1", # Darker border (slate-300)
 "success": "#14b8a6", # Teal for success
 "success_light": "#ccfbf1", # Light teal background
 "warning": "#f59e0b", # Amber
 "warning_light": "#fef3c7", # Light amber background
 "danger": "#ef4444", # Red
 "danger_light": "#fee2e2", # Light red background
 "info": "#14b8a6", # Teal for info
 "info_light": "#ccfbf1", # Light teal background
}

LOGO_URL = "https://cleanenroll.com/CleaningAPP%20logo%20black%20new.png"


def icon(name: str, color: str = "currentColor", size: int = 20) -> str:
 """Deprecated - icons removed from emails for cleaner design"""
 return ""


# Base HTML email template - Clean customer.io style
BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
 <head>
 <meta charset="utf-8" />
 <meta name="viewport" content="width=device-width, initial-scale=1" />
 <meta http-equiv="X-UA-Compatible" content="IE=edge" />
 <title>{{ subject }}</title>
 <style>
 body {
 font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
 -webkit-font-smoothing: antialiased;
 -moz-osx-font-smoothing: grayscale;
 margin: 0;
 padding: 0;
 background-color: #f8fafc;
 }
 table {
 border-collapse: collapse;
 }
 .container {
 max-width: 600px;
 margin: 0 auto;
 }
 .top-border {
 height: 3px;
 background: {{ theme.primary }};
 }
 .content {
 background: #ffffff;
 padding: 48px 40px;
 }
 .title {
 font-size: 24px;
 font-weight: 600;
 color: {{ theme.text_primary }};
 margin: 0 0 16px 0;
 line-height: 1.3;
 }
 .intro {
 font-size: 15px;
 color: {{ theme.text_muted }};
 margin: 0 0 24px 0;
 line-height: 1.5;
 }
 .body-text {
 font-size: 15px;
 color: {{ theme.text_primary }};
 line-height: 1.6;
 }
 .btn {
 display: inline-block;
 background: {{ theme.primary }};
 color: #ffffff !important;
 padding: 12px 24px;
 border-radius: 6px;
 text-decoration: none;
 font-weight: 500;
 font-size: 15px;
 margin: 24px 0;
 }
 .footer {
 padding: 32px 40px;
 text-align: center;
 }
 .footer-text {
 font-size: 13px;
 color: {{ theme.text_muted }};
 margin: 8px 0;
 }
 .footer-link {
 color: {{ theme.text_muted }};
 text-decoration: none;
 }

 @media only screen and (max-width: 600px) {
 .content {
 padding: 32px 24px !important;
 }
 .footer {
 padding: 24px !important;
 }
 .title {
 font-size: 20px !important;
 }
 }
 </style>
 </head>
 <body>
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
 <tr>
 <td align="center" style="padding: 40px 20px;">
 <table role="presentation" class="container" cellpadding="0" cellspacing="0">
 <!-- Top Border -->
 <tr>
 <td class="top-border"></td>
 </tr>

 <!-- Main Content -->
 <tr>
 <td class="content">
 <h1 class="title">{{ title }}</h1>
 {% if intro %}
 <p class="intro">{{ intro }}</p>
 {% endif %}
 <div class="body-text">
 {{ content_html|safe }}
 </div>
 {% if cta_url and cta_label %}
 <div style="text-align: center;">
 <a href="{{ cta_url }}" class="btn">{{ cta_label }}</a>
 </div>
 {% endif %}
 </td>
 </tr>

 <!-- Footer -->
 <tr>
 <td class="footer">
 <p class="footer-text">
 <a href="https://cleanenroll.com/legal#privacy-policy" class="footer-link">Privacy Policy</a>
 &nbsp;•&nbsp;
 <a href="https://cleanenroll.com/legal#terms-of-service" class="footer-link">Terms of Service</a>
 </p>
 <p class="footer-text">
 © {{ year }} CleanEnroll. All rights reserved.
 </p>
 {% if is_user_email %}
 <p class="footer-text" style="font-size: 12px; margin-top: 16px;">
 You're receiving this because you have an account with CleanEnroll.
 </p>
 {% endif %}
 </td>
 </tr>
 </table>
 </td>
 </tr>
 </table>
 </body>
</html>
"""


def render_email(
 subject: str,
 title: str,
 content_html: str,
 intro: Optional[str] = None,
 cta_url: Optional[str] = None,
 cta_label: Optional[str] = None,
 is_user_email: bool = False,
) -> str:
 """Render the email template with provided content"""
 template = Template(BASE_TEMPLATE, autoescape=True)
 return template.render(
 subject=subject,
 title=title,
 intro=intro,
 content_html=content_html,
 cta_url=cta_url,
 cta_label=cta_label,
 theme=THEME,
 logo_url=LOGO_URL,
 year=datetime.now().year,
 is_user_email=is_user_email,
 )


async def send_email(
 to: Union[str, list[str]],
 subject: str,
 title: str,
 content_html: str,
 intro: Optional[str] = None,
 cta_url: Optional[str] = None,
 cta_label: Optional[str] = None,
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
 title: Main heading in the email
 content_html: HTML content for the email body
 intro: Optional intro paragraph (muted text)
 cta_url: Optional call-to-action button URL
 cta_label: Optional call-to-action button text
 from_address: Optional custom from address
 business_config: Optional BusinessConfig for custom SMTP
 is_user_email: Whether this email is to a CleanEnroll user (not a client)
 attachments: Optional list of attachments [{"filename": str, "content": bytes, "content_type": str}]

 Returns:
 Send response dict
 """
 html_content = render_email(
 subject=subject,
 title=title,
 content_html=content_html,
 intro=intro,
 cta_url=cta_url,
 cta_label=cta_label,
 is_user_email=is_user_email,
 )

 # Ensure 'to' is a list
 recipients = [to] if isinstance(to, str) else to
 sender = from_address or EMAIL_FROM_ADDRESS

 # Try custom SMTP first if configured and live
 if business_config and business_config.smtp_status == "live" and business_config.smtp_host:
 try:
 logger.info(f" Sending email via custom SMTP: {business_config.smtp_host}")
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
 logger.warning(f" Custom SMTP failed, falling back to Resend: {e}")
 # Fall through to Resend

 # Fallback to Resend
 if not RESEND_API_KEY:
 logger.error("❌ No email service configured - RESEND_API_KEY missing and no custom SMTP")
 raise Exception("Email service not configured")

 try:
 logger.info(f" Sending email via Resend to: {to}")
 email_data = {
 "from": sender,
 "to": recipients,
 "subject": subject,
 "html": html_content,
 }

 # Add attachments if provided (Resend format)
 if attachments:
 email_data["attachments"] = [
 {"filename": attachment["filename"], "content": attachment["content"]}
 for attachment in attachments
 ]

 response = resend.Emails.send(email_data)
 logger.info(f" Email sent successfully via Resend: {response}")
 return response
 except Exception as e:
 logger.error(f"❌ Email send error to {recipients}: {e}")
 raise Exception(f"Failed to send email: {str(e)}") from e


# ============================================
# Pre-built Email Templates for Common Events
# ============================================


async def send_welcome_email(to: str, user_name: str) -> dict:
 """Send welcome email to new users"""
 content = f"""
 <p>Hi {user_name},</p>
 <p>Welcome to CleanEnroll. We're excited to have you on board.</p>
 <p>With CleanEnroll, you can:</p>
 <ul style="margin: 16px 0; padding-left: 20px; color: {THEME['text_primary']};">
 <li style="margin-bottom: 8px;">Create professional client intake forms</li>
 <li style="margin-bottom: 8px;">Generate contracts automatically</li>
 <li style="margin-bottom: 8px;">Manage your cleaning business efficiently</li>
 </ul>
 <p>Get started by setting up your business profile and creating your first form.</p>
 """
 return await send_email(
 to=to,
 subject="Welcome to CleanEnroll",
 title="Welcome to CleanEnroll",
 intro="Your account has been created successfully.",
 content_html=content,
 cta_url="https://cleanenroll.com/dashboard",
 cta_label="Go to Dashboard",
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

 # Create property shots zip if available
 attachments = None
 property_shots_info = ""

 if property_shots_keys and len(property_shots_keys) > 0:
 try:
 zip_data = await create_property_shots_zip(property_shots_keys, client_name)
 if zip_data:
 # Create safe filename
 safe_client_name = "".join(
 c for c in client_name if c.isalnum() or c in (" ", "-", "_")
 ).rstrip()
 filename = f"property_shots_{safe_client_name.replace(' ', '_')}.zip"

 attachments = [
 {"filename": filename, "content": zip_data, "content_type": "application/zip"}
 ]

 property_shots_info = f"<div style='background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;'><p style='margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;'>Property photos attached as ZIP file ({len(property_shots_keys)} images)</p></div>"
 except Exception as e:
 logger.warning(f"Failed to create property shots zip for {client_name}: {e}")
 property_shots_info = f"<div style='background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;'><p style='margin: 0; color: {THEME['text_primary']}; font-size: 14px;'>Property photos available in dashboard ({len(property_shots_keys)} images)</p></div>"

 content = f"""
 <p>Hi {business_name},</p>
 <p>{client_name} ({client_email}) completed a {property_type} cleaning intake form for {business_name}.</p>

 {property_shots_info}

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Key Details Captured:</h3>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Property type: {property_type}</div>
 <div style="font-size: 14px; color: {THEME['text_muted']};">Full intake details available in dashboard (sq ft, peak hours, security codes, fragile displays)</div>
 </div>
 </div>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <h3 style="margin: 0 0 12px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Next Steps:</h3>
 <p style="margin: 0; font-size: 14px; color: {THEME['text_primary']};">Review property specifics in dashboard → Wait for auto-generated contract to be reviewed and signed by client</p>
 </div>

 <p style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 600;">First booking awaits! </p>

 <p style="margin-top: 20px;">Best,<br/><strong>Cleanenroll Team</strong></p>
 """
 return await send_email(
 to=to,
 subject=f"New {property_type} Property Intake: {client_name} Ready to Review ",
 title="New Client Property Intake Submission",
 content_html=content,
 is_user_email=True,
 attachments=attachments,
 )


async def send_contract_ready_email(
 to: str,
 client_name: str,
 business_name: str,
 contract_pdf_url: str,
) -> dict:
 """Send contract ready notification to client"""
 content = f"""
 <p>Hi {client_name},</p>
 <p>Your service contract with <strong>{business_name}</strong> is ready for review.</p>
 <p>Please download and review the contract. If you have any questions, feel free to reach out to {business_name} directly.</p>
 <div style="background: {THEME['background']}; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
 <p style="margin: 0; color: {THEME['text_muted']}; font-size: 14px;">
 Your contract is attached to this email
 </p>
 </div>
 """
 return await send_email(
 to=to,
 subject=f"Your Contract from {business_name}",
 title="Your Contract is Ready",
 intro="Please review and sign your service agreement.",
 content_html=content,
 cta_url=contract_pdf_url,
 cta_label="Download Contract",
 )


async def send_payment_confirmation(
 to: str,
 user_name: str,
 plan_name: str,
 amount: str,
 next_billing_date: str,
) -> dict:
 """Send payment confirmation email"""
 content = f"""
 <p>Hi {user_name},</p>
 <p>Thank you for your payment! Your subscription has been updated.</p>
 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Plan</div>
 <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{plan_name}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Amount Paid</div>
 <div style="font-weight: 600; font-size: 16px; color: {THEME['success']};">{amount}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Next Billing</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{next_billing_date}</div>
 </div>
 </div>
 <p>You can manage your subscription anytime from your billing settings.</p>
 """
 return await send_email(
 to=to,
 subject="Payment Confirmed - CleanEnroll",
 title="Payment Successful! ",
 intro="Your payment has been processed successfully.",
 content_html=content,
 cta_url="https://cleanenroll.com/billing",
 cta_label="View Billing",
 is_user_email=True,
 )


async def send_password_reset_email(to: str, reset_link: str) -> dict:
 """Send password reset email"""
 content = f"""
 <p>We received a request to reset your password.</p>
 <p>Click the button below to create a new password. This link will expire in 1 hour.</p>
 <p style="margin-top: 24px; padding: 16px; background: {THEME['background']}; border-radius: 8px; font-size: 13px; color: {THEME['text_muted']};">
 If you didn't request this, you can safely ignore this email. Your password won't be changed.
 </p>
 """
 return await send_email(
 to=to,
 subject="Reset Your Password - CleanEnroll",
 title="Reset Your Password",
 content_html=content,
 cta_url=reset_link,
 cta_label="Reset Password",
 is_user_email=True,
 )


async def send_subscription_expiring_email(
 to: str,
 user_name: str,
 plan_name: str,
 expiry_date: str,
) -> dict:
 """Send subscription expiring reminder"""
 content = f"""
 <p>Hi {user_name},</p>
 <p>Your <strong>{plan_name}</strong> subscription is expiring on <strong>{expiry_date}</strong>.</p>
 <p>To continue enjoying all features without interruption, please update your payment method or renew your subscription.</p>
 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px;">
 After expiration, you'll lose access to premium features.
 </p>
 </div>
 """
 return await send_email(
 to=to,
 subject="Your Subscription is Expiring Soon",
 title="Subscription Expiring Soon",
 intro="Don't lose access to your premium features.",
 content_html=content,
 cta_url="https://cleanenroll.com/billing",
 cta_label="Renew Subscription",
 is_user_email=True,
 )


async def send_form_submission_confirmation(
 to: str,
 client_name: str,
 business_name: str,
 property_type: str = "Property",
) -> dict:
 """Send confirmation to client after form submission"""
 content = f"""
 <p>Hi {client_name},</p>
 <p>Thank you for completing your {property_type} cleaning intake form for {business_name}!</p>
 <p>Your property details (square footage, peak hours, security codes, fragile displays) and proposed schedule have been received and processed successfully.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">What's Next:</h3>
 <div style="font-size: 14px; color: {THEME['text_primary']};">
 <div style="margin-bottom: 8px;">Auto-generated contract with dynamic pricing sent to your email</div>
 <div style="margin-bottom: 8px;">Review & sign at your convenience</div>
 <div>{business_name} will review your proposed schedule and confirm</div>
 </div>
 </div>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Quick Confirmation:</h3>
 <div style="font-size: 14px; color: {THEME['text_primary']};">
 <div style="margin-bottom: 8px;">{property_type} property intake completed</div>
 <div style="margin-bottom: 8px;">Proposed schedule submitted</div>
 <div>Ready for your review</div>
 </div>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Questions? Contact {business_name} directly. Excited to get your store sparkling! </p>

 <p style="margin-top: 20px;">Best,<br/><strong>Cleanenroll</strong></p>
 """
 return await send_email(
 to=to,
 subject=f"Thank You for Your {property_type} Cleaning Intake, {client_name}! ",
 title=f"Thank You for Your {property_type} Cleaning Intake, {client_name}! ",
 content_html=content,
 )


async def send_contract_signed_notification(
 to: str,
 business_name: str,
 client_name: str,
 contract_title: str,
) -> dict:
 """Notify business owner when a client signs their contract"""
 content = f"""
 <p>Great news! <strong>{client_name}</strong> has signed their contract.</p>
 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract</div>
 <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{contract_title}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Client</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Status</div>
 <div style="display: inline-flex; align-items: center; gap: 6px; background: {THEME['warning_light']}; color: {THEME['text_primary']}; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
 Awaiting Your Signature
 </div>
 </div>
 </div>

 <div style="background: {THEME['info_light']}; border-left: 3px solid {THEME['info']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-weight: 600; font-size: 14px;">Next Steps:</p>
 <ul style="margin: 12px 0 0 0; padding-left: 20px; color: {THEME['text_secondary']};">
 <li style="margin-bottom: 8px;">Review the schedule submitted by the client</li>
 <li style="margin-bottom: 8px;">Accept the proposed time or suggest an alternative</li>
 <li style="margin-bottom: 8px;">Sign the contract to finalize the agreement</li>
 </ul>
 </div>

 <p>The contract is now awaiting your signature to be fully executed. Review the client's proposed schedule and sign to complete the agreement.</p>
 """
 return await send_email(
 to=to,
 subject=f" Contract Signed by {client_name} - Review Schedule & Sign",
 title="Client Has Signed!",
 intro=f"A contract for {business_name} requires your signature.",
 content_html=content,
 cta_url="https://cleanenroll.com/contracts",
 cta_label="Review & Sign Contract",
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
 content = f"""
 <p>Thank you for signing your contract with <strong>{business_name}</strong>!</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract</div>
 <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{contract_title}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Status</div>
 <div style="display: inline-flex; align-items: center; gap: 6px; background: {THEME['info_light']}; color: {THEME['text_primary']}; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
 Awaiting Provider Signature
 </div>
 </div>
 </div>

 <p>Your signature has been recorded successfully. The service provider will review and sign the contract shortly.</p>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-weight: 600; font-size: 14px;">What happens next?</p>
 <ul style="margin: 12px 0 0 0; padding-left: 20px; color: {THEME['text_secondary']};">
 <li style="margin-bottom: 8px;">The provider will review your proposed schedule</li>
 <li style="margin-bottom: 8px;">They will either accept your time or suggest an alternative</li>
 <li style="margin-bottom: 8px;">Once they sign, you'll receive a confirmation email</li>
 </ul>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 We'll notify you as soon as the contract is fully executed and your schedule is confirmed. If you have any questions, please contact {business_name} directly.
 </p>
 """

 cta_url = contract_pdf_url if contract_pdf_url else None
 cta_label = "View Signed Contract" if contract_pdf_url else None

 return await send_email(
 to=to,
 subject=f" Contract Signed - Awaiting {business_name}",
 title="Thank You for Signing!",
 intro=f"Your contract with {business_name} has been signed successfully.",
 content_html=content,
 cta_url=cta_url,
 cta_label=cta_label,
 is_user_email=False,
 )


async def send_contract_fully_executed_email(
 to: str,
 client_name: str,
 business_name: str,
 contract_title: str,
 contract_id: str, # Now accepts public_id (string UUID)
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

 # Build scheduled time section if applicable
 schedule_section = ""
 if scheduled_time_confirmed and scheduled_start_time:
 schedule_section = f"""
 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0 0 8px 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 First Cleaning Confirmed
 </p>
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px;">
 {scheduled_start_time}
 </p>
 </div>
 """
 elif start_date:
 schedule_section = f"""
 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px; text-align: center;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Your signed contract PDF is attached. Your schedule has been confirmed!
 </p>
 </div>
 """
 else:
 schedule_section = f"""
 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px; text-align: center;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Your signed contract PDF is attached. Your schedule has been confirmed!
 </p>
 </div>
 """

 content = f"""
 <p>Hi {client_name},</p>
 <p>Perfect! <strong>{business_name}</strong> has reviewed and signed your service agreement{f' for {property_address}' if property_address else ''}.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
 <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Quick Details:</h3>
 <div style="space-y: 12px;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract ID</div>
 <div style="font-weight: 600; font-size: 15px; color: {THEME['text_primary']}; font-family: monospace;">{contract_id}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Service Type</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{service_type}</div>
 </div>
 {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Total</div><div style="font-weight: 600; font-size: 16px; color: {THEME["primary"]};">${total_value:,.2f}</div></div>' if total_value else ''}
 </div>
 </div>

 {schedule_section}

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Questions? Reply here{f' or call {business_phone}' if business_phone else ''}.
 </p>
 <p style="margin-top: 20px;">Clean regards,<br/><strong>{business_name} Team</strong></p>
 """
 return await send_email(
 to=to,
 subject=f"Great News! Your Cleaning Contract is Fully Signed & Ready [Contract {contract_id}]",
 title="Contract Fully Signed!",
 intro=f"{business_name} has reviewed and signed your service agreement.",
 content_html=content,
 cta_url=contract_pdf_url,
 cta_label="Download Signed Contract" if contract_pdf_url else None,
 )


async def send_provider_contract_signed_confirmation(
 to: str,
 provider_name: str,
 contract_id: str, # Now accepts public_id (string UUID)
 client_name: str,
 property_address: Optional[str] = None,
 contract_pdf_url: Optional[str] = None,
) -> dict:
 """Send provider-only confirmation after they sign a contract"""
 content = f"""
 <p>Hi {provider_name},</p>
 <p>Contract <strong>{contract_id}</strong> for {client_name}{f' ({property_address})' if property_address else ''} is fully executed. Client has been notified.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract ID</div>
 <div style="font-weight: 600; font-size: 15px; color: {THEME['text_primary']}; font-family: monospace;">{contract_id}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Client</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Property</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{property_address}</div></div>' if property_address else ''}
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Schedule confirmed - Ready to start service
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">The client's proposed schedule has been reviewed and confirmed. Signed PDF attached.</p>
 """
 return await send_email(
 to=to,
 subject=f"You've Signed Contract - Client Notification Sent",
 title="Contract Signed Successfully",
 intro="The contract has been fully executed.",
 content_html=content,
 cta_url=contract_pdf_url,
 cta_label="View Signed Contract" if contract_pdf_url else None,
 is_user_email=True,
 )


async def send_scheduling_proposal_email(
 client_email: str,
 client_name: str,
 provider_name: str,
 contract_id: str, # Now accepts public_id (string UUID)
 time_slots: list,
 expires_at: str,
) -> dict:
 """Send scheduling proposal to client with available time slots"""
 # Format time slots for display
 slots_html = ""
 for i, slot in enumerate(time_slots, 1):
 recommended = (
 f" <span style='color: {THEME['primary']}; font-weight: 600;'> Recommended</span>"
 if slot.get("recommended")
 else ""
 )
 slots_html += f"""
 <div style="background: {THEME['background']}; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 4px;">Option {i}{recommended}</div>
 <div style="color: {THEME['text_muted']}; font-size: 14px;">
 {slot.get('date')} | {slot.get('start_time')} - {slot.get('end_time')}
 </div>
 </div>
 """

 # Generate scheduling response URL
 scheduling_url = f"http://localhost:5173/scheduling/{contract_id}"

 content = f"""
 <p>Hi {client_name},</p>
 <p>{provider_name} has proposed the following time slots for your service. Please review and select your preferred time:</p>

 <div style="margin: 24px 0;">
 {slots_html}
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Tip: Click the button below to select a time slot or suggest your own preferred times!
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">This proposal expires on {expires_at}. Please respond before then.</p>
 """

 return await send_email(
 to=client_email,
 subject=f"Scheduling Proposal for Contract {contract_id}",
 title="Service Scheduling Proposal",
 intro="Please select your preferred time slot.",
 content_html=content,
 cta_url=scheduling_url,
 cta_label="Select Time Slot",
 )


async def send_scheduling_accepted_email(
 provider_email: str,
 provider_name: str,
 client_name: str,
 contract_id: str, # Now accepts public_id (string UUID)
 selected_date: str,
 start_time: str,
 end_time: str,
 property_address: Optional[str] = None,
) -> dict:
 """Notify provider when client accepts a time slot"""
 content = f"""
 <p>Hi {provider_name},</p>
 <p>{client_name} has accepted a time slot for Contract <span style="font-family: monospace; font-weight: 600;">{contract_id}</span>:</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Scheduled Date</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{selected_date}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Time</div>
 <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{start_time} - {end_time}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{property_address}</div></div>' if property_address else ''}
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Appointment confirmed
 </p>
 </div>
 """

 return await send_email(
 to=provider_email,
 subject=f"Time Slot Accepted for Contract {contract_id}",
 title="Scheduling Confirmed",
 intro=f"{client_name} has accepted your proposed time.",
 content_html=content,
 is_user_email=True,
 )


async def send_scheduling_counter_proposal_email(
 provider_email: str,
 provider_name: str,
 client_name: str,
 contract_id: str, # Now accepts public_id (string UUID)
 preferred_days: Optional[str] = None,
 time_window: Optional[str] = None,
 client_notes: Optional[str] = None,
) -> dict:
 """Notify provider when client proposes alternative times"""
 content = f"""
 <p>Hi {provider_name},</p>
 <p>{client_name} has suggested alternative scheduling preferences for Contract <span style="font-family: monospace; font-weight: 600;">{contract_id}</span>:</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
 {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Preferred Days</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{preferred_days}</div></div>' if preferred_days else ''}
 {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Time Window</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{time_window}</div></div>' if time_window else ''}
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Client Notes</div><div style="font-size: 15px; color: {THEME["text_primary"]}; font-style: italic;">"{client_notes}"</div></div>' if client_notes else ''}
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Counter-proposal received - Please review and respond
 </p>
 </div>
 """

 return await send_email(
 to=provider_email,
 subject=f"Alternative Times Proposed for Contract {contract_id}",
 title="Scheduling Counter-Proposal",
 intro=f"{client_name} has suggested different times.",
 content_html=content,
 is_user_email=True,
 )


async def send_email_verification_otp(to: str, user_name: str, otp: str) -> dict:
 """Send OTP for email verification"""
 content = f"""
 <p>Hi {user_name},</p>
 <p>To verify your email address, please use the verification code below:</p>

 <div style="background: {THEME['background']}; border-radius: 16px; padding: 32px; margin: 32px 0; text-align: center;">
 <div style="color: {THEME['text_muted']}; font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Your Verification Code</div>
 <div style="font-size: 42px; font-weight: 700; letter-spacing: 8px; color: {THEME['primary']}; font-family: 'Courier New', monospace; text-align: center;">
 {otp}
 </div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-top: 12px;">This code expires in 10 minutes</div>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Enter this code in the verification page to confirm your email address.
 </p>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 13px;">
 If you didn't request this code, you can safely ignore this email.
 </p>
 </div>
 """
 return await send_email(
 to=to,
 subject="Verify Your Email - CleanEnroll",
 title="Verify Your Email Address",
 intro="Please confirm your email to secure your account.",
 content_html=content,
 is_user_email=True,
 )


async def send_appointment_notification(
 provider_email: str,
 provider_name: str,
 client_name: str,
 appointment_time: datetime,
 location: Optional[str] = None,
 event_link: Optional[str] = None,
) -> dict:
 """Notify provider when client schedules an appointment (pending approval)"""
 formatted_time = appointment_time.strftime("%A, %B %d, %Y at %I:%M %p")

 content = f"""
 <p>Hi {provider_name},</p>
 <p><strong>{client_name}</strong> has requested their first cleaning appointment.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Requested Date & Time</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_time}</div>
 </div>
 {f'<div style="margin-bottom: 16px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{location}</div></div>' if location else ''}
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Client</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
 </div>
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Action Required: Please review and accept or request a different time
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Visit your Schedule page to accept this appointment or propose an alternative time to the client.
 </p>
 """

 return await send_email(
 to=provider_email,
 subject=f"Pending Appointment Request: {client_name} - {appointment_time.strftime('%b %d, %Y')}",
 title="New Appointment Request",
 intro=f"{client_name} has requested a cleaning appointment.",
 content_html=content,
 is_user_email=True,
 )


async def send_appointment_confirmation(
 client_email: str,
 client_name: str,
 provider_name: str,
 appointment_time: datetime,
 location: Optional[str] = None,
 event_link: Optional[str] = None,
) -> dict:
 """Confirm appointment to client after provider accepts"""
 formatted_time = appointment_time.strftime("%A, %B %d, %Y at %I:%M %p")

 content = f"""
 <p>Hi {client_name},</p>
 <p>Great news! <strong>{provider_name}</strong> has confirmed your cleaning appointment.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Confirmed Date & Time</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_time}</div>
 </div>
 {f'<div style="margin-bottom: 16px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{location}</div></div>' if location else ''}
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Service Provider</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{provider_name}</div>
 </div>
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Your appointment is confirmed and has been added to your calendar
 </p>
 </div>

 {f'<p style="text-align: center; margin: 24px 0;"><a href="{event_link}" style="display: inline-block; background: {THEME["primary"]}; color: white; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px;">Add to Calendar →</a></p>' if event_link else ''}
 """

 return await send_email(
 to=client_email,
 subject=f"Appointment Confirmed - {appointment_time.strftime('%b %d, %Y')}",
 title="Appointment Confirmed!",
 intro=f"Your cleaning appointment with {provider_name} is confirmed.",
 content_html=content,
 )


async def send_schedule_change_request(
 client_email: str,
 client_name: str,
 provider_name: str,
 original_time: datetime,
 proposed_time: datetime,
 proposed_start: str,
 proposed_end: str,
 schedule_id: int,
 client_id: int = None,
) -> dict:
 """Notify client when provider requests alternative time"""
 import hashlib

 original_formatted = original_time.strftime("%A, %B %d, %Y at %I:%M %p")
 proposed_formatted = proposed_time.strftime("%A, %B %d, %Y")

 # Generate secure token for the response link
 token = ""
 response_url = ""
 if client_id:
 data = f"{schedule_id}:{client_id}:cleanenroll_schedule_secret"
 token = hashlib.sha256(data.encode()).hexdigest()[:32]
 response_url = f"{FRONTEND_URL}/schedule-response/{schedule_id}?token={token}"

 content = f"""
 <p>Hi {client_name},</p>
 <p><strong>{provider_name}</strong> has reviewed your appointment request and would like to propose an alternative time.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 20px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Your Requested Time</div>
 <div style="font-size: 15px; color: {THEME['text_muted']}; text-decoration: line-through;">{original_formatted}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Proposed Alternative</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{proposed_formatted} from {proposed_start} to {proposed_end}</div>
 </div>
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Response Needed: Please confirm or suggest another time
 </p>
 </div>
 """

 # Add CTA button if we have a response URL
 cta_url = response_url if response_url else None
 cta_label = "Respond to Proposal" if response_url else None

 return await send_email(
 to=client_email,
 subject=f"Alternative Time Proposed by {provider_name}",
 title="Alternative Time Proposed",
 intro=f"{provider_name} has suggested a different appointment time.",
 content_html=content,
 cta_url=cta_url,
 cta_label=cta_label,
 )


async def send_client_accepted_proposal(
 provider_email: str,
 provider_name: str,
 client_name: str,
 accepted_date: datetime,
 accepted_start_time: str,
 accepted_end_time: str,
 schedule_id: int,
) -> dict:
 """Notify provider when client accepts their proposed alternative time"""
 date_formatted = accepted_date.strftime("%A, %B %d, %Y")

 content = f"""
 <p>Hi {provider_name},</p>
 <p>Great news! <strong>{client_name}</strong> has accepted your proposed appointment time.</p>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 24px; margin: 24px 0; border-radius: 4px;">
 <div style="color: {THEME['text_primary']}; font-size: 13px; margin-bottom: 6px;">Confirmed Appointment</div>
 <div style="font-size: 18px; color: {THEME['text_primary']}; font-weight: 600;">{date_formatted}</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; margin-top: 4px;">{accepted_start_time} - {accepted_end_time}</div>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 The appointment has been confirmed and added to your schedule. You can view the details in your dashboard.
 </p>
 """

 return await send_email(
 to=provider_email,
 subject=f"{client_name} Accepted Your Proposed Time",
 title="Appointment Confirmed!",
 intro=f"{client_name} has confirmed the appointment.",
 content_html=content,
 cta_url=f"{FRONTEND_URL}/dashboard/schedule",
 cta_label="View Schedule",
 is_user_email=True,
 )


async def send_appointment_confirmed_to_client(
 client_email: str,
 client_name: str,
 provider_name: str,
 confirmed_date: datetime,
 confirmed_start_time: str,
 confirmed_end_time: str,
) -> dict:
 """Send confirmation email to client after they accept a proposed time"""
 date_formatted = confirmed_date.strftime("%A, %B %d, %Y")

 content = f"""
 <p>Hi {client_name},</p>
 <p>Your appointment with <strong>{provider_name}</strong> has been confirmed!</p>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 24px; margin: 24px 0; border-radius: 4px;">
 <div style="color: {THEME['text_primary']}; font-size: 13px; margin-bottom: 6px;">Confirmed Appointment</div>
 <div style="font-size: 18px; color: {THEME['text_primary']}; font-weight: 600;">{date_formatted}</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; margin-top: 4px;">{confirmed_start_time} - {confirmed_end_time}</div>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 {provider_name} will arrive at the scheduled time. If you need to make any changes, please contact them directly.
 </p>
 """

 return await send_email(
 to=client_email,
 subject=f"Appointment Confirmed with {provider_name}",
 title="Appointment Confirmed!",
 intro="Your appointment has been scheduled.",
 content_html=content,
 )


async def send_schedule_accepted_confirmation_to_provider(
 provider_email: str,
 provider_name: str,
 client_name: str,
 confirmed_date: date,
 confirmed_start_time: str,
 confirmed_end_time: str,
 client_address: Optional[str] = None,
) -> dict:
 """Notify provider after they accept a schedule"""
 formatted_date = confirmed_date.strftime("%A, %B %d, %Y")

 content = f"""
 <p>Hi {provider_name},</p>
 <p>You've successfully confirmed the appointment for <strong>{client_name}</strong>. The client has been notified.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Appointment Date</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_date}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Time</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{confirmed_start_time} - {confirmed_end_time}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Client</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{client_address}</div></div>' if client_address else ''}
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Appointment confirmed and client notified
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 The appointment has been added to your schedule. You can view all your appointments in the Schedule page.
 </p>
 """

 return await send_email(
 to=provider_email,
 subject=f" Appointment Confirmed - {client_name} on {formatted_date}",
 title="Appointment Confirmed!",
 intro="You've successfully confirmed the appointment.",
 content_html=content,
 cta_url="https://cleanenroll.com/schedule",
 cta_label="View Schedule",
 is_user_email=True,
 )


async def send_client_counter_proposal(
 provider_email: str,
 provider_name: str,
 client_name: str,
 original_proposed_date: datetime,
 client_preferred_date: datetime,
 client_preferred_start: str,
 client_preferred_end: str,
 client_reason: str,
 schedule_id: int,
) -> dict:
 """Notify provider when client suggests an alternative time"""
 original_formatted = original_proposed_date.strftime("%A, %B %d, %Y")
 preferred_formatted = client_preferred_date.strftime("%A, %B %d, %Y")

 content = f"""
 <p>Hi {provider_name},</p>
 <p><strong>{client_name}</strong> has reviewed your proposed time and would like to suggest an alternative.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 20px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Your Proposed Time</div>
 <div style="font-size: 15px; color: {THEME['text_muted']}; text-decoration: line-through;">{original_formatted}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Client's Preferred Time</div>
 <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{preferred_formatted}</div>
 <div style="font-size: 14px; color: {THEME['text_primary']}; margin-top: 4px;">{client_preferred_start} - {client_preferred_end}</div>
 </div>
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0 0 8px 0; color: {THEME['text_primary']}; font-size: 13px; font-weight: 600;">Client's Reason:</p>
 <p style="margin: 0; color: {THEME['text_secondary']}; font-size: 14px; font-style: italic;">"{client_reason}"</p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Please review the client's suggestion and respond through your dashboard.
 </p>
 """

 return await send_email(
 to=provider_email,
 subject=f" {client_name} Suggested an Alternative Time",
 title="Alternative Time Suggested",
 intro=f"{client_name} has suggested a different appointment time.",
 content_html=content,
 cta_url=f"{FRONTEND_URL}/dashboard/schedule",
 cta_label="Review in Dashboard",
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
 recurrence_pattern: Optional[str] = None,
) -> dict:
 """Send invoice with payment link to client"""

 # Format recurring info
 recurring_info = ""
 if is_recurring and recurrence_pattern:
 recurring_info = f"""
 <div style="background: {THEME['info_light']}; border-left: 3px solid {THEME['info']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 This is a recurring payment ({recurrence_pattern}). Your card will be charged automatically.
 </p>
 </div>
 """

 content = f"""
 <p>Hi {client_name},</p>
 <p>Your invoice from <strong>{business_name}</strong> is ready for payment.</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Invoice Number</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 600;">{invoice_number}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Service</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{invoice_title}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Amount Due</div>
 <div style="font-size: 24px; color: {THEME['primary']}; font-weight: 700;">${total_amount:,.2f} {currency}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">Due Date</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{due_date}</div></div>' if due_date else ''}
 </div>

 {recurring_info}

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Click the button below to pay securely online
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 Questions about this invoice? Contact {business_name} directly.
 </p>
 """

 return await send_email(
 to=to,
 subject=f"Invoice {invoice_number} from {business_name} - Payment Ready",
 title="Your Invoice is Ready",
 intro=f"Please review and pay your invoice from {business_name}.",
 content_html=content,
 cta_url=payment_link,
 cta_label="Pay Now",
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

 content = f"""
 <p>Hi {provider_name},</p>
 <p>Excellent news! <strong>{client_name}</strong> has just paid their invoice.</p>

 <div style="background: {THEME['success_light']}; border-radius: 8px; padding: 28px; margin: 24px 0; text-align: center;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 8px;">Payment Received</div>
 <div style="font-size: 36px; color: {THEME['success']}; font-weight: 600; margin-bottom: 8px;">
 ${amount:,.2f} {currency}
 </div>
 </div>

 <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Invoice Number</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{invoice_number}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Client</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{client_name}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Payment Date</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{payment_date}</div></div>' if payment_date else ''}
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 4px;">Ready for Payout</div>
 <p style="color: {THEME['text_secondary']}; margin: 0; font-size: 14px; line-height: 1.6;">
 This payment has been added to your available balance and is ready for withdrawal.
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px; margin-top: 24px;">
 Ready to withdraw? Visit your payouts dashboard to request a withdrawal to your bank account.
 </p>
 """

 return await send_email(
 to=provider_email,
 subject=f"Payment Received: ${amount:,.2f} from {client_name}",
 title="Payment Received!",
 intro=f"Great news! {client_name} has paid invoice {invoice_number}.",
 content_html=content,
 cta_url=f"{FRONTEND_URL}/dashboard/payouts",
 cta_label="View Payouts Dashboard",
 is_user_email=True,
 )


async def send_payment_thank_you_email(
 client_email: str,
 client_name: str,
 business_name: str,
 invoice_number: str,
 amount: float,
 currency: str = "USD",
 service_date: Optional[str] = None,
) -> dict:
 """Send thank you email to client after successful payment"""

 content = f"""
 <p>Hi {client_name},</p>
 <p>Thank you for your payment to <strong>{business_name}</strong>!</p>

 <div style="background: {THEME['background']}; border-radius: 12px; padding: 24px; margin: 24px 0;">
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Invoice Number</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 600;">{invoice_number}</div>
 </div>
 <div style="margin-bottom: 16px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">Amount Paid</div>
 <div style="font-size: 24px; color: {THEME['success']}; font-weight: 700;">${amount:,.2f} {currency}</div>
 </div>
 {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">Service Date</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{service_date}</div></div>' if service_date else ''}
 </div>

 <div style="background: {THEME['success_light']}; border-left: 3px solid {THEME['success']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <p style="margin: 0; color: {THEME['text_primary']}; font-size: 14px; font-weight: 600;">
 Your payment has been processed successfully
 </p>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 We look forward to providing you with excellent service. If you have any questions, please contact {business_name} directly.
 </p>

 <p style="margin-top: 24px;">Thank you for your business! </p>
 """

 return await send_email(
 to=client_email,
 subject=f"Payment Confirmed - Thank You! - {business_name}",
 title="Thank You for Your Payment!",
 intro=f"Your payment to {business_name} has been received.",
 content_html=content,
 )


async def send_contract_cancelled_email(
 client_email: str,
 client_name: str,
 contract_title: str,
 business_name: str,
 business_config=None,
) -> dict:
 """Send contract cancellation notification to client"""

 content = f"""
 <p>Dear {client_name},</p>
 <p>We're writing to inform you that your service contract has been cancelled.</p>

 <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 16px;">Contract Details</div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 600;">{contract_title}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Service Provider</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{business_name}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Status</div>
 <div style="display: inline-flex; align-items: center; gap: 6px; background: {THEME['danger_light']}; color: {THEME['danger']}; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
 Cancelled
 </div>
 </div>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px;">
 If you have any questions about this cancellation or would like to discuss future services, please don't hesitate to contact {business_name}.
 </p>

 <p style="margin-top: 20px;">Thank you for your understanding.</p>

 <p style="margin-top: 20px;">Best regards,<br/><strong>{business_name}</strong></p>
 """

 return await send_email(
 to=client_email,
 subject=f"Contract Cancelled - {contract_title}",
 title="Contract Cancelled",
 intro="Your service contract has been cancelled.",
 content_html=content,
 business_config=business_config,
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
    """Notify provider when client books an appointment (pending approval)"""
    
    # Calculate duration if not provided
    if duration_minutes:
        duration_text = f"{duration_minutes} minutes"
    else:
        duration_text = "Duration not specified"
    
    content = f"""
    <p>Hi {provider_name},</p>
    <p>A client has selected their preferred time for the first cleaning session.</p>
    
    <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
        <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 16px;">Requested Cleaning Schedule</div>
        <div style="space-y: 12px;">
            <div style="margin-bottom: 12px;">
                <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Date</div>
                <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{scheduled_date}</div>
            </div>
            <div style="margin-bottom: 12px;">
                <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Time</div>
                <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{start_time} – {end_time}</div>
            </div>
            <div>
                <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Duration</div>
                <div style="font-size: 15px; color: {THEME['text_primary']};">{duration_text}</div>
            </div>
        </div>
    </div>
    
    <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
        <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">Action Required</div>
        <p style="color: {THEME['text_secondary']}; margin: 0; font-size: 14px; line-height: 1.6;">
            Please review this request in your dashboard and confirm the schedule, or propose an alternative time if necessary.
        </p>
    </div>
    
    <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
        <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 16px;">Client Details</div>
        <div style="space-y: 12px;">
            <div style="margin-bottom: 12px;">
                <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Name</div>
                <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{client_name}</div>
            </div>
            {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Email</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{client_email}</div></div>' if client_email else ''}
            {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Phone</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{client_phone}</div></div>' if client_phone else ''}
        </div>
    </div>
    """

    return await send_email(
        to=provider_email,
        subject=f"New Schedule Request, {client_name}",
        title="New Schedule Request",
        intro="A client has selected their preferred time for the first cleaning session.",
        content_html=content,
        cta_url=f"{FRONTEND_URL}/dashboard/schedule",
        cta_label="Review Schedule",
        is_user_email=True,
    )


# ============================================
# Quote Approval Email Templates
# ============================================


async def send_quote_submitted_confirmation(
    to: str,
    client_name: str,
    business_name: str,
    quote_amount: float,
) -> dict:
    """Send confirmation email to client after they approve the automated quote"""
    content = f"""
    <p>Hi {client_name},</p>
    <p>Thank you for submitting your quote request. We've received your approval and {business_name} will review it shortly.</p>
    
    <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 8px;">Estimated Quote</div>
        <div style="font-size: 32px; font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">
            ${quote_amount:,.2f}
        </div>
        <div style="font-size: 14px; color: {THEME['text_muted']};">
            This is an automated estimate. Final pricing will be confirmed by {business_name}.
        </div>
    </div>
    
    <div style="background: {THEME['info_light']}; border-left: 3px solid {THEME['primary']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
        <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">What happens next?</div>
        <ol style="color: {THEME['text_secondary']}; margin: 8px 0; padding-left: 20px; line-height: 1.6;">
            <li style="margin-bottom: 6px;">{business_name} will review your quote and service requirements</li>
            <li style="margin-bottom: 6px;">They may approve it as-is or make adjustments based on your specific needs</li>
            <li style="margin-bottom: 6px;">You'll receive an email with the final approved quote</li>
            <li>The email will include a button to schedule your first cleaning</li>
        </ol>
    </div>
    
    <p style="color: {THEME['text_muted']}; font-size: 14px;">
        <strong>Expected response time:</strong> Within 24-48 hours
    </p>
    
    <p style="color: {THEME['text_muted']}; font-size: 14px; margin-top: 20px;">
        Questions? Contact {business_name} directly for assistance.
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Your Quote Request Has Been Submitted - {business_name}",
        title="Quote Request Submitted",
        intro=f"Thank you for your interest in {business_name}'s services.",
        content_html=content,
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
 # Generate review link
 review_link = f"{FRONTEND_URL}/dashboard/quote-requests"

 content = f"""
 <p>Hi {provider_name},</p>
 <p>A client has approved an automated estimate and is awaiting your review.</p>

 <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 16px;">Client Details</div>
 <div style="space-y: 12px;">
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Name</div>
 <div style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 500;">{client_name}</div>
 </div>
 <div style="margin-bottom: 12px;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Email</div>
 <div style="font-size: 15px; color: {THEME['text_primary']};">{client_email}</div>
 </div>
 <div>
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Automated Estimate</div>
 <div style="font-size: 24px; color: {THEME['text_primary']}; font-weight: 600;">${quote_amount:,.2f}</div>
 </div>
 </div>
 </div>

 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">Action Required</div>
 <p style="color: {THEME['text_secondary']}; margin: 0; font-size: 14px; line-height: 1.6;">
 Please review the estimate and either approve it as-is or adjust the pricing based on the client's specific requirements or site conditions.
 </p>
 <p style="color: {THEME['text_secondary']}; margin: 12px 0 0 0; font-size: 14px; line-height: 1.6;">
 Once approved, the client will be prompted to schedule their first cleaning, sign the MSA, and complete payment.
 </p>
 </div>
 """

 return await send_email(
 to=to,
 subject=f"New Quote Review Required, {client_name}",
 title=f"New Quote Review Required",
 intro="A client has approved an automated estimate and is awaiting your review.",
 content_html=content,
 cta_url=review_link,
 cta_label="Review & Approve Quote",
 is_user_email=True,
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
 # Generate scheduling link - goes to client schedule page which will handle contract generation
 schedule_link = f"{os.getenv('FRONTEND_URL', 'https://app.cleanenroll.com')}/client-schedule/{client_public_id}"

 adjustment_section = ""
 if was_adjusted and adjustment_notes:
 adjustment_section = f"""
 <div style="background: {THEME['warning_light']}; border-left: 3px solid {THEME['warning']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">Quote Adjusted</div>
 <p style="color: {THEME['text_secondary']}; margin: 0; font-size: 14px; line-height: 1.6;">
 {adjustment_notes}
 </p>
 </div>
 """

 content = f"""
 <p>Hi {client_name},</p>
 <p>Great news! {business_name} has reviewed and approved your quote. You're ready to schedule your first cleaning!</p>

 <div style="background: {THEME['background']}; border-radius: 8px; padding: 24px; margin: 24px 0; text-align: center;">
 <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 8px;">Final Approved Quote</div>
 <div style="font-size: 36px; font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">
 ${final_quote_amount:,.2f}
 </div>
 </div>

 {adjustment_section}

 <div style="background: {THEME['info_light']}; border-left: 3px solid {THEME['primary']}; padding: 16px; margin: 24px 0; border-radius: 4px;">
 <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 8px;">Next Steps:</div>
 <ol style="color: {THEME['text_secondary']}; margin: 8px 0; padding-left: 20px; line-height: 1.6;">
 <li style="margin-bottom: 6px;">Click the button below to choose your preferred date and time</li>
 <li style="margin-bottom: 6px;">Review and sign the service agreement</li>
 <li style="margin-bottom: 6px;">Receive your invoice and complete payment</li>
 <li>Get ready for your first cleaning!</li>
 </ol>
 </div>

 <p style="color: {THEME['text_muted']}; font-size: 14px; margin-top: 24px;">
 Questions? Contact {business_name} directly for assistance.
 </p>
 """

 subject = "Your Quote Has Been Approved - Schedule Your First Cleaning"
 if was_adjusted:
 subject = "Your Quote Has Been Updated - Schedule Your First Cleaning"

 return await send_email(
 to=to,
 subject=f"{subject} - {business_name}",
 title="Your Quote Has Been Approved!" if not was_adjusted else "Your Quote Has Been Updated",
 intro=f"{business_name} has reviewed and approved your quote.",
 content_html=content,
 cta_url=schedule_link,
 cta_label="Schedule Your First Cleaning",
 )
