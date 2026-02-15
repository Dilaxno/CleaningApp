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

        logger.info(f"✅ Custom SMTP email sent successfully via {business_config.smtp_host}")
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
            for i, key in enumerate(property_shots_keys[:12]):  # Limit to 12 images
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


# App theme colors - Modern, professional palette
THEME = {
    "primary": "#00C4B4",  # Teal - primary brand color
    "primary_dark": "#00A89A",  # Darker teal for hover
    "primary_light": "#E6FAF8",  # Light teal background
    "background": "#F8FAFC",  # Soft gray background
    "card_bg": "#FFFFFF",  # White card background
    "text_primary": "#0F172A",  # Rich dark text
    "text_secondary": "#334155",  # Secondary text
    "text_muted": "#64748B",  # Muted gray text
    "border": "#E2E8F0",  # Light border
    "border_dark": "#CBD5E1",  # Darker border
    "success": "#10B981",  # Modern green
    "success_light": "#D1FAE5",  # Light green background
    "warning": "#F59E0B",  # Amber
    "warning_light": "#FEF3C7",  # Light amber background
    "danger": "#EF4444",  # Red
    "info": "#3B82F6",  # Blue
    "info_light": "#DBEAFE",  # Light blue background
}

LOGO_URL = "https://cleanenroll.com/CleaningAPP%20logo%20black%20new.png"

# Premium SVG Icons
ICONS = {
    "calendar": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="6" width="18" height="15" rx="2" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 3v4M16 3v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "clock": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "location": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="9" r="2.5" stroke="currentColor" stroke-width="2"/></svg>""",
    "user": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2"/><path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "check": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="#22c55e"/><path d="M8 12l3 3 5-6" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>""",
    "money": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="6" width="20" height="12" rx="2" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/><path d="M18 10v4M6 10v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "document": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "video": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="6" width="14" height="12" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 10l6-3v10l-6-3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>""",
    "sparkles": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2z" fill="currentColor"/><path d="M18 3l1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3z" fill="currentColor"/></svg>""",
    "warning": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L2 20h20L12 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 9v4M12 17h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "info": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 16v-4M12 8h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "building": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="2" width="16" height="20" rx="2" stroke="currentColor" stroke-width="2"/><path d="M9 22V18h6v4M8 6h2M14 6h2M8 10h2M14 10h2M8 14h2M14 14h2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>""",
    "chat": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>""",
    "image": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"/><path d="M21 15l-5-5L5 21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>""",
}


def icon(name: str, color: str = "currentColor", size: int = 20) -> str:
    """Get an SVG icon with specified color and size"""
    svg = ICONS.get(name, ICONS["info"])
    # Replace currentColor with actual color and adjust size
    svg = svg.replace('width="24"', f'width="{size}"')
    svg = svg.replace('height="24"', f'height="{size}"')
    svg = svg.replace("currentColor", color)
    return (
        f'<span style="display: inline-block; vertical-align: middle; line-height: 0;">{svg}</span>'
    )


# Base HTML email template - Modern Akkio-style with clean top bar
BASE_TEMPLATE = """
<!doctype html>
<html lang="en" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta name="x-apple-disable-message-reformatting" />
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no" />
    <title>{{ subject }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <style>
      body, table, td, a, h1, h2, h3, p, strong, em, span, div {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }
      body {
        width: 100% !important;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
        margin: 0;
        padding: 0;
      }
      img {
        max-width: 100%;
        height: auto;
        border: 0;
        line-height: 100%;
        outline: none;
        text-decoration: none;
        -ms-interpolation-mode: bicubic;
      }
      table {
        border-collapse: collapse !important;
        mso-table-lspace: 0pt;
        mso-table-rspace: 0pt;
      }
      .container {
        max-width: 600px;
        margin: 0 auto;
        width: 100%;
      }
      .top-bar {
        height: 4px;
        background: {{ theme.primary }};
        width: 100%;
      }
      .card {
        background: {{ theme.card_bg }};
        border-radius: 8px;
        padding: 40px;
        border: 1px solid {{ theme.border }};
        margin-top: 32px;
      }
      .muted { color: {{ theme.text_muted }}; }
      .btn {
        display: inline-block;
        background: {{ theme.primary }};
        color: #ffffff !important;
        padding: 12px 32px;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        line-height: 1.5;
        text-align: center;
      }
      .btn:hover {
        background: {{ theme.primary_dark }};
        opacity: 0.9;
      }

      /* Mobile Responsive Styles */
      @media only screen and (max-width: 600px) {
        .container {
          padding: 0 16px !important;
          width: 100% !important;
        }
        .card {
          padding: 28px 20px !important;
          border-radius: 6px !important;
          margin-top: 24px !important;
        }
        .btn {
          display: block !important;
          width: 100% !important;
          padding: 14px 24px !important;
          font-size: 15px !important;
          box-sizing: border-box;
        }
        img.logo {
          max-width: 160px !important;
          height: auto !important;
        }
        h1 {
          font-size: 20px !important;
          line-height: 1.3 !important;
        }
        h2 {
          font-size: 17px !important;
          line-height: 1.4 !important;
        }
        p, div, td {
          font-size: 14px !important;
          line-height: 1.6 !important;
        }
      }

      /* Dark Mode Support */
      @media (prefers-color-scheme: dark) {
        .card {
          background: #1e293b !important;
          border-color: #334155 !important;
        }
      }
    </style>
    <!--[if gte mso 9]>
    <xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
    <![endif]-->
  </head>
  <body style="margin:0; padding:0; background:{{ theme.background }}; color:{{ theme.text_primary }};">
    <!-- Top Colored Bar -->
    <div class="top-bar"></div>

    <div class="container" style="padding: 32px 20px;">
      <!-- Logo -->
      <div style="text-align:center; margin-bottom:8px;">
        <a href="https://cleanenroll.com" target="_blank" style="text-decoration:none;">
          <img class="logo" src="{{ logo_url }}" width="180" alt="CleanEnroll"
               style="display:block; height:auto; border:0; margin:0 auto;" />
        </a>
      </div>

      <!-- Card -->
      <div class="card">
        <h1 style="margin:0 0 12px 0; font-size:22px; font-weight:700; color:{{ theme.text_primary }}; letter-spacing:-0.01em;">
          {{ title }}
        </h1>

        {% if intro %}
        <p style="margin:0 0 24px 0; font-size:15px; line-height:1.6; color:{{ theme.text_muted }};">
          {{ intro }}
        </p>
        {% endif %}

        <div style="font-size:15px; line-height:1.65; color:{{ theme.text_primary }};">
          {{ content_html|safe }}
        </div>

        {% if cta_url and cta_label %}
        <!--[if mso]>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 0 0;">
          <tr><td>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{{ cta_url }}"
                         style="height:44px; v-text-anchor:middle; width:180px;" arcsize="15%"
                         stroke="f" fillcolor="{{ theme.primary }}">
              <center style="color:#ffffff; font-family:Arial,sans-serif; font-size:15px; font-weight:600;">
                {{ cta_label }}
              </center>
            </v:roundrect>
          </td></tr>
        </table>
        <![endif]-->
        <!--[if !mso]><!-->
        <div style="margin:24px 0 0 0; text-align:center;">
          <a class="btn" href="{{ cta_url }}">{{ cta_label }}</a>
        </div>
        <!--<![endif]-->
        {% endif %}
      </div>

      <!-- Footer -->
      <div style="text-align:center; margin-top:32px; padding-top:24px; border-top:1px solid {{ theme.border }};">
        <p class="muted" style="font-size:13px; line-height:1.6; margin:0 0 8px 0; color:{{ theme.text_muted }};">
          <a href="https://cleanenroll.com/legal#privacy-policy" style="color:{{ theme.text_muted }}; text-decoration:none; margin:0 8px;">Privacy Policy</a>
          <span style="color:#cbd5e1;">•</span>
          <a href="https://cleanenroll.com/legal#terms-of-service" style="color:{{ theme.text_muted }}; text-decoration:none; margin:0 8px;">Terms of Service</a>
        </p>
        <p class="muted" style="font-size:12px; margin:8px 0 0 0; color:#94a3b8;">
          © {{ year }} CleanEnroll. All rights reserved.
        </p>
        {% if is_user_email %}
        <p style="color:#94a3b8; font-size:11px; margin:12px 0 0 0;">
          You're receiving this because you have an account with CleanEnroll.
        </p>
        {% endif %}
      </div>
    </div>
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
            # Fall through to Resend

    # Fallback to Resend
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

        # Add attachments if provided (Resend format)
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
# ============================================


async def send_welcome_email(to: str, user_name: str) -> dict:
    """Send welcome email to new users"""
    content = f"""
    <p>Hi {user_name},</p>
    <p>Welcome to CleanEnroll! We're excited to have you on board.</p>
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
        title="Welcome to CleanEnroll!",
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

                property_shots_info = f"<div style='background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;'><p style='margin: 0; color: #166534; font-size: 14px; font-weight: 600;'>{icon('image', '#22c55e', 18)} Property photos attached as ZIP file ({len(property_shots_keys)} images)</p></div>"
        except Exception as e:
            logger.warning(f"Failed to create property shots zip for {client_name}: {e}")
            property_shots_info = f"<div style='background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;'><p style='margin: 0; color: #92400e; font-size: 14px;'>{icon('warning', '#f59e0b', 18)} Property photos available in dashboard ({len(property_shots_keys)} images)</p></div>"

    content = f"""
    <p>Hi {business_name},</p>
    <p>{client_name} ({client_email}) completed a {property_type} cleaning intake form for {business_name}.</p>

    {property_shots_info}

    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
      <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">{icon('building', THEME['primary'], 20)} Key Details Captured:</h3>
      <div style="margin-bottom: 12px;">
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Property type: {property_type}</div>
        <div style="font-size: 14px; color: {THEME['text_muted']};">Full intake details available in dashboard (sq ft, peak hours, security codes, fragile displays)</div>
      </div>
    </div>

    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
      <h3 style="margin: 0 0 12px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">{icon('sparkles', THEME['primary'], 20)} Next Steps:</h3>
      <p style="margin: 0; font-size: 14px; color: {THEME['text_primary']};">Review property specifics in dashboard → Wait for auto-generated contract to be reviewed and signed by client</p>
    </div>

    <p style="font-size: 15px; color: {THEME['text_primary']}; font-weight: 600;">First booking awaits! {icon('check', THEME['success'], 20)}</p>

    <p style="margin-top: 20px;">Best,<br/><strong>Cleanenroll Team</strong></p>
    """
    return await send_email(
        to=to,
        subject=f"New {property_type} Property Intake: {client_name} Ready to Review",
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
        📄 Your contract is attached to this email
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
        title="Payment Successful! ✓",
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
    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
      <p style="margin: 0; color: #92400e; font-size: 14px;">
        ⚠️ After expiration, you'll lose access to premium features.
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
        <div style="margin-bottom: 8px;">{icon('check', THEME['success'], 18)} Auto-generated contract with dynamic pricing sent to your email</div>
        <div style="margin-bottom: 8px;">{icon('check', THEME['success'], 18)} Review & sign at your convenience</div>
        <div>{icon('check', THEME['success'], 18)} {business_name} will review your proposed schedule and confirm</div>
      </div>
    </div>

    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
      <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Quick Confirmation:</h3>
      <div style="font-size: 14px; color: {THEME['text_primary']};">
        <div style="margin-bottom: 8px;">{icon('check', THEME['success'], 18)} {property_type} property intake completed</div>
        <div style="margin-bottom: 8px;">{icon('check', THEME['success'], 18)} Proposed schedule submitted</div>
        <div>{icon('check', THEME['success'], 18)} Ready for your review</div>
      </div>
    </div>

    <p style="color: {THEME['text_muted']}; font-size: 14px;">
      Questions? Contact {business_name} directly. Excited to get your store sparkling! {icon('sparkles', THEME['primary'], 18)}
    </p>

    <p style="margin-top: 20px;">Best,<br/><strong>Cleanenroll</strong></p>
    """
    return await send_email(
        to=to,
        subject=f"Thank You for Your {property_type} Cleaning Intake, {client_name}",
        title=f"Thank You for Your {property_type} Cleaning Intake, {client_name}",
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
        <div style="display: inline-flex; align-items: center; gap: 6px; background: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
          {icon('clock', '#f59e0b', 16)} Awaiting Your Signature
        </div>
      </div>
    </div>

    <div style="background: #e0f2fe; border-left: 4px solid #0ea5e9; padding: 16px; margin: 20px 0; border-radius: 8px;">
      <p style="margin: 0; color: #0369a1; font-weight: 600; font-size: 14px;">{icon('calendar', '#0ea5e9', 18)} Next Steps:</p>
      <ul style="margin: 12px 0 0 0; padding-left: 20px; color: #0369a1;">
        <li style="margin-bottom: 8px;">Review the schedule submitted by the client</li>
        <li style="margin-bottom: 8px;">Accept the proposed time or suggest an alternative</li>
        <li style="margin-bottom: 8px;">Sign the contract to finalize the agreement</li>
      </ul>
    </div>

    <p>The contract is now awaiting your signature to be fully executed. Review the client's proposed schedule and sign to complete the agreement.</p>
    """
    return await send_email(
        to=to,
        subject=f"Contract Signed by {client_name} - Review Schedule & Sign",
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
        <div style="display: inline-flex; align-items: center; gap: 6px; background: #dbeafe; color: #1e40af; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
          {icon('clock', '#1e40af', 16)} Awaiting Provider Signature
        </div>
      </div>
    </div>

    <p>Your signature has been recorded successfully. The service provider will review and sign the contract shortly.</p>

    <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px; margin: 20px 0; border-radius: 8px;">
      <p style="margin: 0; color: #166534; font-weight: 600; font-size: 14px;">{icon('check', '#22c55e', 18)} What happens next?</p>
      <ul style="margin: 12px 0 0 0; padding-left: 20px; color: #166534;">
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
        subject=f"Contract Signed - Awaiting {business_name}",
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
    contract_id: str,  # Now accepts public_id (string UUID)
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
        <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
          <p style="margin: 0 0 8px 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('check', '#22c55e', 18)} First Cleaning Confirmed
          </p>
          <p style="margin: 0; color: #166534; font-size: 14px;">
            {icon('calendar', '#166534', 18)} {scheduled_start_time}
          </p>
        </div>
        """
    elif start_date:
        schedule_section = f"""
        <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
          <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('check', '#22c55e', 18)} Your signed contract PDF is attached. Your schedule has been confirmed!
          </p>
        </div>
        """
    else:
        schedule_section = f"""
        <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
          <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('sparkles', '#22c55e', 18)} Your signed contract PDF is attached. Your schedule has been confirmed!
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
    contract_id: str,  # Now accepts public_id (string UUID)
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
      <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
        {icon('check', '#22c55e', 18)} Schedule confirmed - Ready to start service
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
    contract_id: str,  # Now accepts public_id (string UUID)
    time_slots: list,
    expires_at: str,
) -> dict:
    """Send scheduling proposal to client with available time slots"""
    # Format time slots for display
    slots_html = ""
    for i, slot in enumerate(time_slots, 1):
        recommended = (
            " <span style='color: #00C4B4; font-weight: 600;'>⭐ Recommended</span>"
            if slot.get("recommended")
            else ""
        )
        slots_html += f"""
        <div style="background: {THEME['background']}; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
            <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 4px;">Option {i}{recommended}</div>
            <div style="color: {THEME['text_muted']}; font-size: 14px;">
                {icon('calendar', THEME['muted'], 16)} {slot.get('date')} | {icon('clock', THEME['muted'], 16)} {slot.get('start_time')} - {slot.get('end_time')}
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('info', '#22c55e', 18)} Tip: Click the button below to select a time slot or suggest your own preferred times!
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
    contract_id: str,  # Now accepts public_id (string UUID)
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['primary'], 18)} Scheduled Date</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{selected_date}</div>
        </div>
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('clock', THEME['primary'], 18)} Time</div>
            <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{start_time} - {end_time}</div>
        </div>
        {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{property_address}</div></div>' if property_address else ''}
    </div>

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('check', '#22c55e', 18)} Appointment confirmed
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
    contract_id: str,  # Now accepts public_id (string UUID)
    preferred_days: Optional[str] = None,
    time_window: Optional[str] = None,
    client_notes: Optional[str] = None,
) -> dict:
    """Notify provider when client proposes alternative times"""
    content = f"""
    <p>Hi {provider_name},</p>
    <p>{client_name} has suggested alternative scheduling preferences for Contract <span style="font-family: monospace; font-weight: 600;">{contract_id}</span>:</p>

    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">{icon("calendar", THEME["primary"], 18)} Preferred Days</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{preferred_days}</div></div>' if preferred_days else ''}
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">{icon("clock", THEME["primary"], 18)} Time Window</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{time_window}</div></div>' if time_window else ''}
        {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">{icon("chat", THEME["primary"], 18)} Client Notes</div><div style="font-size: 15px; color: {THEME["text_primary"]}; font-style: italic;">"{client_notes}"</div></div>' if client_notes else ''}
    </div>

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
            {icon('clock', '#f59e0b', 18)} Counter-proposal received - Please review and respond
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

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 13px;">
            {icon('warning', '#f59e0b', 18)} If you didn't request this code, you can safely ignore this email.
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['primary'], 18)} Requested Date & Time</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_time}</div>
        </div>
        {f'<div style="margin-bottom: 16px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">{icon("location", THEME["primary"], 18)} Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{location}</div></div>' if location else ''}
        <div>
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('user', THEME['primary'], 18)} Client</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
        </div>
    </div>

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
            {icon('clock', '#f59e0b', 18)} Action Required: Please review and accept or request a different time
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['primary'], 18)} Confirmed Date & Time</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_time}</div>
        </div>
        {f'<div style="margin-bottom: 16px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">{icon("location", THEME["primary"], 18)} Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{location}</div></div>' if location else ''}
        <div>
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('building', THEME['primary'], 18)} Service Provider</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{provider_name}</div>
        </div>
    </div>

    <div style="background: #d1fae5; border: 1px solid #10b981; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #065f46; font-size: 14px; font-weight: 600;">
            {icon('check', '#10b981', 18)} Your appointment is confirmed and has been added to your calendar
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['muted'], 18)} Your Requested Time</div>
            <div style="font-size: 15px; color: {THEME['text_muted']}; text-decoration: line-through;">{original_formatted}</div>
        </div>
        <div>
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('sparkles', THEME['primary'], 18)} Proposed Alternative</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{proposed_formatted} from {proposed_start} to {proposed_end}</div>
        </div>
    </div>

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
            {icon('clock', '#f59e0b', 18)} Response Needed: Please confirm or suggest another time
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 24px; margin: 24px 0;">
        <div style="color: #166534; font-size: 13px; margin-bottom: 6px;">{icon('check', '#22c55e', 18)} Confirmed Appointment</div>
        <div style="font-size: 18px; color: #166534; font-weight: 600;">{date_formatted}</div>
        <div style="font-size: 15px; color: #166534; margin-top: 4px;">{accepted_start_time} - {accepted_end_time}</div>
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 24px; margin: 24px 0;">
        <div style="color: #166534; font-size: 13px; margin-bottom: 6px;">{icon('check', '#22c55e', 18)} Confirmed Appointment</div>
        <div style="font-size: 18px; color: #166534; font-weight: 600;">{date_formatted}</div>
        <div style="font-size: 15px; color: #166534; margin-top: 4px;">{confirmed_start_time} - {confirmed_end_time}</div>
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['primary'], 18)} Appointment Date</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{formatted_date}</div>
        </div>
        <div style="margin-bottom: 16px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('clock', THEME['primary'], 18)} Time</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{confirmed_start_time} - {confirmed_end_time}</div>
        </div>
        <div style="margin-bottom: 16px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('user', THEME['primary'], 18)} Client</div>
            <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
        </div>
        {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 6px;">{icon("location", THEME["primary"], 18)} Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{client_address}</div></div>' if client_address else ''}
    </div>

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('check', '#22c55e', 18)} Appointment confirmed and client notified
        </p>
    </div>

    <p style="color: {THEME['text_muted']}; font-size: 14px;">
        The appointment has been added to your schedule. You can view all your appointments in the Schedule page.
    </p>
    """

    return await send_email(
        to=provider_email,
        subject=f"Appointment Confirmed - {client_name} on {formatted_date}",
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
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('calendar', THEME['muted'], 18)} Your Proposed Time</div>
            <div style="font-size: 15px; color: {THEME['text_muted']}; text-decoration: line-through;">{original_formatted}</div>
        </div>
        <div>
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 6px;">{icon('sparkles', THEME['primary'], 18)} Client's Preferred Time</div>
            <div style="font-size: 16px; color: {THEME['text_primary']}; font-weight: 600;">{preferred_formatted}</div>
            <div style="font-size: 14px; color: {THEME['text_primary']}; margin-top: 4px;">{client_preferred_start} - {client_preferred_end}</div>
        </div>
    </div>

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 8px 0; color: #92400e; font-size: 13px; font-weight: 600;">{icon('chat', '#f59e0b', 18)} Client's Reason:</p>
        <p style="margin: 0; color: #92400e; font-size: 14px; font-style: italic;">"{client_reason}"</p>
    </div>

    <p style="color: {THEME['text_muted']}; font-size: 14px;">
        Please review the client's suggestion and respond through your dashboard.
    </p>
    """

    return await send_email(
        to=provider_email,
        subject=f"{client_name} Suggested an Alternative Time",
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
        <div style="background: #e0f2fe; border: 1px solid #0ea5e9; border-radius: 12px; padding: 16px; margin: 20px 0;">
            <p style="margin: 0; color: #0369a1; font-size: 14px; font-weight: 600;">
                🔄 This is a recurring payment ({recurrence_pattern}). Your card will be charged automatically.
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('money', '#22c55e', 18)} Click the button below to pay securely online
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
    <p>{icon('sparkles', THEME['primary'], 20)} <strong>Excellent news!</strong> <strong>{client_name}</strong> has just paid their invoice.</p>

    <div style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); border: 2px solid #22c55e; border-radius: 16px; padding: 28px; margin: 24px 0; box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);">
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="display: inline-block; background: #22c55e; color: white; padding: 12px; border-radius: 50%; margin-bottom: 12px;">
                <svg style="width: 24px; height: 24px; fill: currentColor;" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4 4a2 2 0 00-2 2v4a2 2 0 002 2V6h10a2 2 0 00-2-2H4zm2 6a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-4zm6 4a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd" />
                </svg>
            </div>
            <div style="font-size: 32px; color: #22c55e; font-weight: 800; margin-bottom: 8px;">${amount:,.2f} {currency}</div>
            <div style="color: #166534; font-size: 16px; font-weight: 600;">Payment Received!</div>
        </div>

        <div style="background: rgba(255, 255, 255, 0.8); border-radius: 12px; padding: 20px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div>
                    <div style="color: #166534; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Invoice</div>
                    <div style="font-size: 15px; color: #166534; font-weight: 600;">{invoice_number}</div>
                </div>
                <div>
                    <div style="color: #166534; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Client</div>
                    <div style="font-size: 15px; color: #166534; font-weight: 600;">{client_name}</div>
                </div>
            </div>
            {f'<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(34, 197, 94, 0.2);"><div style="color: #166534; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Payment Date</div><div style="font-size: 15px; color: #166534; font-weight: 600;">{payment_date}</div></div>' if payment_date else ''}
        </div>
    </div>

    <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 2px solid #f59e0b; border-radius: 12px; padding: 20px; margin: 20px 0;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="background: #f59e0b; color: white; padding: 8px; border-radius: 50%; flex-shrink: 0;">
                <svg style="width: 20px; height: 20px; fill: currentColor;" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
                </svg>
            </div>
            <div>
                <div style="color: #92400e; font-size: 14px; font-weight: 700; margin-bottom: 2px;">{icon('money', '#f59e0b', 18)} Ready for Payout</div>
                <div style="color: #92400e; font-size: 13px;">This payment has been added to your available balance and is ready for withdrawal.</div>
            </div>
        </div>
    </div>

    <p style="color: {THEME['text_muted']}; font-size: 14px; text-align: center; margin-top: 24px;">
        {icon('sparkles', THEME['primary'], 18)} <strong>Ready to withdraw?</strong> Visit your payouts dashboard to request a withdrawal to your bank account.
    </p>
    """

    return await send_email(
        to=provider_email,
        subject=f"Payment Received: ${amount:,.2f} from {client_name}",
        title="Payment Received",
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

    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            {icon('check', '#22c55e', 18)} Your payment has been processed successfully
        </p>
    </div>

    <p style="color: {THEME['text_muted']}; font-size: 14px;">
        We look forward to providing you with excellent service. If you have any questions, please contact {business_name} directly.
    </p>

    <p style="margin-top: 24px;">Thank you for your business! {icon('sparkles', THEME['primary'], 18)}</p>
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

    <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 20px; margin: 24px 0;">
        <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #dc2626;">{icon('warning', '#dc2626', 20)} Contract Details</h3>
        <div style="margin-bottom: 12px;">
            <div style="color: #7f1d1d; font-size: 13px; margin-bottom: 4px;">Contract</div>
            <div style="font-size: 15px; color: #7f1d1d; font-weight: 600;">{contract_title}</div>
        </div>
        <div style="margin-bottom: 12px;">
            <div style="color: #7f1d1d; font-size: 13px; margin-bottom: 4px;">Service Provider</div>
            <div style="font-size: 15px; color: #7f1d1d;">{business_name}</div>
        </div>
        <div>
            <div style="color: #7f1d1d; font-size: 13px; margin-bottom: 4px;">Status</div>
            <div style="display: inline-flex; align-items: center; gap: 6px; background: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
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
) -> dict:
    """Notify provider when client books an appointment (pending approval)"""

    content = f"""
    <p>Hi {provider_name},</p>
    <p><strong>{client_name}</strong> has requested a cleaning appointment and is awaiting your approval.</p>

    <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0;">
        <div style="margin-bottom: 16px;">
            <div style="color: #64748b; font-size: 13px; margin-bottom: 6px;">{icon('calendar', '#00C4B4', 18)} Requested Date</div>
            <div style="font-size: 16px; color: #1e293b; font-weight: 600;">{scheduled_date}</div>
        </div>
        <div style="margin-bottom: 16px;">
            <div style="color: #64748b; font-size: 13px; margin-bottom: 6px;">{icon('clock', '#00C4B4', 18)} Time</div>
            <div style="font-size: 16px; color: #1e293b; font-weight: 600;">{start_time} - {end_time}</div>
        </div>
        {f'<div style="margin-bottom: 16px;"><div style="color: #64748b; font-size: 13px; margin-bottom: 6px;">{icon("location", "#00C4B4", 18)} Location</div><div style="font-size: 15px; color: #1e293b;">{property_address}</div></div>' if property_address else ''}
        <div>
            <div style="color: #64748b; font-size: 13px; margin-bottom: 6px;">{icon('user', '#00C4B4', 18)} Client</div>
            <div style="font-size: 15px; color: #1e293b;">{client_name}</div>
        </div>
    </div>

    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
            {icon('clock', '#f59e0b', 18)} Action Required: Accept this appointment or propose an alternative time
        </p>
    </div>

    <p style="color: #64748b; font-size: 14px;">
        Visit your Schedule page to review and respond to this booking request.
    </p>
    """

    return await send_email(
        to=provider_email,
        subject=f"New Booking Request from {client_name} - Action Needed",
        title="New Appointment Request",
        intro=f"{client_name} has requested a cleaning appointment.",
        content_html=content,
        cta_url=f"{FRONTEND_URL}/dashboard/schedule",
        cta_label="Review Request",
        is_user_email=True,
        business_config=None,
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
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">Quote Submitted!</h1>
        </div>
        
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; margin-bottom: 20px;">
                Hi {client_name},
            </p>
            
            <p style="font-size: 16px; color: #374151; line-height: 1.6; margin-bottom: 20px;">
                Thank you for submitting your quote request! We've received your approval and {business_name} will review it shortly.
            </p>
            
            <div style="background: white; border: 2px solid #10b981; border-radius: 8px; padding: 20px; margin: 25px 0;">
                <h3 style="color: #059669; margin-top: 0; font-size: 18px;">Estimated Quote</h3>
                <p style="font-size: 32px; font-weight: bold; color: #1f2937; margin: 10px 0;">
                    ${quote_amount:,.2f}
                </p>
                <p style="font-size: 14px; color: #6b7280; margin: 0;">
                    This is an automated estimate. Final pricing will be confirmed by {business_name}.
                </p>
            </div>
            
            <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin: 25px 0; border-radius: 4px;">
                <h4 style="color: #1e40af; margin-top: 0; font-size: 16px;">What happens next?</h4>
                <ol style="color: #1e3a8a; margin: 10px 0; padding-left: 20px; line-height: 1.8;">
                    <li>{business_name} will review your quote and service requirements</li>
                    <li>They may approve it as-is or make adjustments based on your specific needs</li>
                    <li>You'll receive an email with the final approved quote</li>
                    <li>The email will include a button to schedule your first cleaning</li>
                </ol>
            </div>
            
            <p style="font-size: 14px; color: #6b7280; margin-top: 25px;">
                <strong>Expected response time:</strong> Within 24-48 hours
            </p>
            
            <p style="font-size: 14px; color: #6b7280; margin-top: 20px;">
                Questions? Contact {business_name} directly for assistance.
            </p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #9ca3af; text-align: center; margin: 0;">
                This is an automated message from {business_name}
            </p>
        </div>
    </div>
    """

    return await send_email(
        to=to,
        subject=f"Your Quote Request Has Been Submitted - {business_name}",
        title="Quote Request Submitted",
        content_html=content,
        intro=f"Thank you for your interest in {business_name}'s services!",
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
    review_link = f"{FRONTEND_URL}/dashboard/clients?review={client_public_id}"
    
    content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">New Quote Approval Request</h1>
        </div>
        
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; margin-bottom: 20px;">
                Hi {provider_name},
            </p>
            
            <p style="font-size: 16px; color: #374151; line-height: 1.6; margin-bottom: 20px;">
                <strong>{client_name}</strong> has approved an automated quote and is waiting for your review.
            </p>
            
            <div style="background: white; border: 2px solid #f59e0b; border-radius: 8px; padding: 20px; margin: 25px 0;">
                <h3 style="color: #d97706; margin-top: 0; font-size: 18px;">Client Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Name:</td>
                        <td style="padding: 8px 0; color: #1f2937; font-size: 14px; font-weight: 600;">{client_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Email:</td>
                        <td style="padding: 8px 0; color: #1f2937; font-size: 14px;">{client_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Automated Quote:</td>
                        <td style="padding: 8px 0; color: #1f2937; font-size: 18px; font-weight: bold;">${quote_amount:,.2f}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 25px 0; border-radius: 4px;">
                <p style="color: #92400e; margin: 0; font-size: 14px; line-height: 1.6;">
                    <strong>Action Required:</strong> Please review this quote and either approve it as-is or make adjustments based on the client's specific requirements.
                </p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{review_link}" 
                   style="display: inline-block; background: #f59e0b; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                    Review & Approve Quote
                </a>
            </div>
            
            <p style="font-size: 14px; color: #6b7280; margin-top: 25px;">
                <strong>Recommended response time:</strong> Within 24-48 hours
            </p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #9ca3af; text-align: center; margin: 0;">
                This is an automated notification from CleanEnroll
            </p>
        </div>
    </div>
    """

    return await send_email(
        to=to,
        subject=f"New Quote Approval Request from {client_name}",
        title="New Quote Approval Request",
        content_html=content,
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
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 25px 0; border-radius: 4px;">
            <h4 style="color: #92400e; margin-top: 0; font-size: 16px;">Quote Adjusted</h4>
            <p style="color: #92400e; margin: 0; font-size: 14px; line-height: 1.6;">
                {adjustment_notes}
            </p>
        </div>
        """
    
    content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">Your Quote Has Been Approved!</h1>
        </div>
        
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; margin-bottom: 20px;">
                Hi {client_name},
            </p>
            
            <p style="font-size: 16px; color: #374151; line-height: 1.6; margin-bottom: 20px;">
                Great news! {business_name} has reviewed and approved your quote. You're ready to schedule your first cleaning!
            </p>
            
            <div style="background: white; border: 2px solid #10b981; border-radius: 8px; padding: 20px; margin: 25px 0; text-align: center;">
                <h3 style="color: #059669; margin-top: 0; font-size: 18px;">Final Approved Quote</h3>
                <p style="font-size: 36px; font-weight: bold; color: #1f2937; margin: 10px 0;">
                    ${final_quote_amount:,.2f}
                </p>
            </div>
            
            {adjustment_section}
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{schedule_link}" 
                   style="display: inline-block; background: #10b981; color: white; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 18px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    Schedule Your First Cleaning
                </a>
            </div>
            
            <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin: 25px 0; border-radius: 4px;">
                <h4 style="color: #1e40af; margin-top: 0; font-size: 16px;">Next Steps:</h4>
                <ol style="color: #1e3a8a; margin: 10px 0; padding-left: 20px; line-height: 1.8;">
                    <li>Click the button above to choose your preferred date and time</li>
                    <li>Review and sign the service agreement</li>
                    <li>Receive your invoice and complete payment</li>
                    <li>Get ready for your first cleaning!</li>
                </ol>
            </div>
            
            <p style="font-size: 14px; color: #6b7280; margin-top: 25px;">
                Questions? Contact {business_name} directly for assistance.
            </p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #9ca3af; text-align: center; margin: 0;">
                This is an automated message from {business_name}
            </p>
        </div>
    </div>
    """

    subject = "Your Quote Has Been Approved - Schedule Your First Cleaning"
    if was_adjusted:
        subject = "Your Quote Has Been Updated - Schedule Your First Cleaning"

    return await send_email(
        to=to,
        subject=f"{subject} - {business_name}",
        title=subject,
        content_html=content,
    )
