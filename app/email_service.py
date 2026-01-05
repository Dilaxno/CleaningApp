"""
Unified Email Service using Resend
Provides a consistent email template for all automated emails
"""
import resend
from datetime import datetime
from typing import Optional, Union, List
from jinja2 import Template
from .config import RESEND_API_KEY, EMAIL_FROM_ADDRESS

# Initialize Resend
resend.api_key = RESEND_API_KEY

# App theme colors
THEME = {
    "primary": "#00C4B4",      # Teal - primary brand color
    "primary_dark": "#00A89A", # Darker teal for hover
    "background": "#f8f9fb",   # Light gray background
    "card_bg": "#ffffff",      # White card background
    "text_primary": "#1E293B", # Dark text
    "text_muted": "#64748B",   # Muted gray text
    "border": "#e2e8f0",       # Light border
    "success": "#22c55e",      # Green
    "warning": "#f59e0b",      # Amber
    "danger": "#ef4444",       # Red
}

LOGO_URL = "https://res.cloudinary.com/dxqum9ywx/image/upload/v1767444587/CleaningAPP_logo_black_z96svy.png"

# Base HTML email template
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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <style>
      body, table, td, a, h1, h2, h3, p, strong, em, span, div { 
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }
      body {
        width: 100% !important;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
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
        max-width: 640px; 
        margin: 0 auto;
        width: 100%;
      }
      .card { 
        background: {{ theme.card_bg }}; 
        border-radius: 16px; 
        padding: 32px; 
        border: 1px solid {{ theme.border }};
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
      }
      .muted { color: {{ theme.text_muted }}; }
      .btn {
        display: inline-block;
        background: {{ theme.primary }};
        color: #ffffff !important;
        padding: 14px 28px;
        border-radius: 12px;
        text-decoration: none;
        font-weight: 600;
        font-size: 16px;
        line-height: 1.5;
        transition: all 0.2s;
        min-width: 200px;
        text-align: center;
        -webkit-tap-highlight-color: rgba(0, 0, 0, 0.1);
      }
      .btn:hover { background: {{ theme.primary_dark }}; }
      .badge {
        display: inline-flex;
        align-items: center;
        background: {{ theme.primary }};
        color: #ffffff !important;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
      }
      
      /* Mobile Responsive Styles */
      @media only screen and (max-width: 600px) {
        .container { 
          padding: 0 12px !important;
          width: 100% !important;
        }
        .card { 
          padding: 24px 20px !important;
          border-radius: 12px !important;
        }
        .btn { 
          display: block !important;
          width: 100% !important;
          max-width: 100% !important;
          min-width: auto !important;
          padding: 16px 24px !important;
          font-size: 15px !important;
          box-sizing: border-box;
        }
        img.logo { 
          max-width: 140px !important;
          height: auto !important;
        }
        h1 {
          font-size: 22px !important;
          line-height: 1.3 !important;
        }
        h2 {
          font-size: 18px !important;
          line-height: 1.4 !important;
        }
        p, div, td {
          font-size: 14px !important;
          line-height: 1.6 !important;
        }
        .mobile-hide {
          display: none !important;
          max-height: 0 !important;
          overflow: hidden !important;
          mso-hide: all !important;
        }
        .mobile-stack {
          display: block !important;
          width: 100% !important;
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
  <body style="margin:0; padding:32px 16px; background:{{ theme.background }}; color:{{ theme.text_primary }};">
    <div class="container">
      <!-- Logo -->
      <div style="text-align:center; margin-bottom:24px;">
        <a href="https://cleanenroll.com" target="_blank" style="text-decoration:none;">
          <img class="logo" src="{{ logo_url }}" width="160" alt="CleanEnroll" 
               style="display:block; height:auto; border:0; margin:0 auto;" />
        </a>
      </div>

      <!-- Card -->
      <div class="card">
        <h1 style="margin:0 0 16px 0; font-size:24px; font-weight:700; color:{{ theme.text_primary }};">
          {{ title }}
        </h1>

        {% if intro %}
        <p style="margin:0 0 20px 0; font-size:16px; line-height:1.6; color:{{ theme.text_muted }};">
          {{ intro }}
        </p>
        {% endif %}

        <div style="font-size:15px; line-height:1.7; color:{{ theme.text_primary }};">
          {{ content_html|safe }}
        </div>

        {% if cta_url and cta_label %}
        <!--[if mso]>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 0 0;">
          <tr><td>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{{ cta_url }}" 
                         style="height:48px; v-text-anchor:middle; width:200px;" arcsize="25%" 
                         stroke="f" fillcolor="{{ theme.primary }}">
              <center style="color:#ffffff; font-family:Arial,sans-serif; font-size:16px; font-weight:600;">
                {{ cta_label }}
              </center>
            </v:roundrect>
          </td></tr>
        </table>
        <![endif]-->
        <!--[if !mso]><!-->
        <p style="margin:28px 0 0 0;">
          <a class="btn" href="{{ cta_url }}">{{ cta_label }}</a>
        </p>
        <!--<![endif]-->
        {% endif %}
      </div>

      <!-- Footer -->
      <p class="muted" style="font-size:12px; text-align:center; margin-top:24px; line-height:1.6;">
        © {{ year }} CleanEnroll • 
        <a href="https://cleanenroll.com/legal#privacy-policy" style="color:{{ theme.primary }}; text-decoration:none;">Privacy</a> • 
        <a href="https://cleanenroll.com/legal#terms-of-service" style="color:{{ theme.primary }}; text-decoration:none;">Terms</a>
        <br/>
        <span style="color:#94a3b8; font-size:11px;">You're receiving this because you have an account with CleanEnroll.</span>
      </p>
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
) -> str:
    """Render the email template with provided content"""
    template = Template(BASE_TEMPLATE)
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
    )


async def send_email(
    to: Union[str, List[str]],
    subject: str,
    title: str,
    content_html: str,
    intro: Optional[str] = None,
    cta_url: Optional[str] = None,
    cta_label: Optional[str] = None,
    from_address: Optional[str] = None,
) -> dict:
    """
    Send an email using Resend with the unified template
    
    Args:
        to: Recipient email(s)
        subject: Email subject line
        title: Main heading in the email
        content_html: HTML content for the email body
        intro: Optional intro paragraph (muted text)
        cta_url: Optional call-to-action button URL
        cta_label: Optional call-to-action button text
        from_address: Optional custom from address
    
    Returns:
        Resend API response
    """
    if not RESEND_API_KEY:
        print("Warning: RESEND_API_KEY not configured, skipping email")
        return {"error": "Email not configured"}
    
    html_content = render_email(
        subject=subject,
        title=title,
        content_html=content_html,
        intro=intro,
        cta_url=cta_url,
        cta_label=cta_label,
    )
    
    # Ensure 'to' is a list
    recipients = [to] if isinstance(to, str) else to
    
    try:
        response = resend.Emails.send({
            "from": from_address or EMAIL_FROM_ADDRESS,
            "to": recipients,
            "subject": subject,
            "html": html_content,
        })
        return response
    except Exception as e:
        print(f"Email send error: {e}")
        return {"error": str(e)}


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
        subject="Welcome to CleanEnroll! 🎉",
        title="Welcome to CleanEnroll!",
        intro="Your account has been created successfully.",
        content_html=content,
        cta_url="https://cleanenroll.com/dashboard",
        cta_label="Go to Dashboard",
    )


async def send_new_client_notification(
    to: str,
    business_name: str,
    client_name: str,
    client_email: str,
    property_type: str,
) -> dict:
    """Notify business owner of new client submission"""
    content = f"""
    <p>Great news! You have a new client submission.</p>
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 20px 0;">
      <div style="margin-bottom: 12px;">
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Client Name</div>
        <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">{client_name}</div>
      </div>
      <div style="margin-bottom: 12px;">
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Email</div>
        <div style="font-size: 15px; color: {THEME['primary']};">{client_email}</div>
      </div>
      <div>
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Property Type</div>
        <div style="font-size: 15px; color: {THEME['text_primary']}; text-transform: capitalize;">{property_type}</div>
      </div>
    </div>
    <p>Review their submission and send a quote to get started.</p>
    """
    return await send_email(
        to=to,
        subject=f"New Client Submission: {client_name}",
        title="New Client Submission",
        intro=f"A new client has submitted a form for {business_name}.",
        content_html=content,
        cta_url="https://cleanenroll.com/clients",
        cta_label="View Client Details",
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
    )


async def send_form_submission_confirmation(
    to: str,
    client_name: str,
    business_name: str,
) -> dict:
    """Send confirmation to client after form submission"""
    content = f"""
    <p>Hi {client_name},</p>
    <p>Thank you for submitting your information to <strong>{business_name}</strong>!</p>
    <p>Your submission has been received and is being reviewed. You can expect to hear back soon with next steps.</p>
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
      <p style="margin: 0; color: {THEME['text_muted']}; font-size: 14px;">
        ✓ Submission received successfully
      </p>
    </div>
    <p style="color: {THEME['text_muted']}; font-size: 14px;">
      If you have any questions, please contact {business_name} directly.
    </p>
    """
    return await send_email(
        to=to,
        subject=f"Submission Received - {business_name}",
        title="Thank You for Your Submission!",
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
          ⏳ Awaiting Your Signature
        </div>
      </div>
    </div>
    <p>The contract is now awaiting your signature to be fully executed. Review and sign to complete the agreement.</p>
    """
    return await send_email(
        to=to,
        subject=f"🖊️ Contract Signed by {client_name} - Action Required",
        title="Client Has Signed!",
        intro=f"A contract for {business_name} requires your signature.",
        content_html=content,
        cta_url="https://cleanenroll.com/contracts",
        cta_label="Review & Sign Contract",
    )


async def send_contract_fully_executed_email(
    to: str,
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_id: int,
    service_type: str,
    start_date: Optional[str] = None,
    total_value: Optional[float] = None,
    property_address: Optional[str] = None,
    business_phone: Optional[str] = None,
    contract_pdf_url: Optional[str] = None,
) -> dict:
    """Notify client when contract is fully signed by both parties"""
    content = f"""
    <p>Hi {client_name},</p>
    <p>Perfect! <strong>{business_name}</strong> has reviewed and signed your service agreement{f' for {property_address}' if property_address else ''}.</p>
    
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
      <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: {THEME['text_primary']};">Quick Details:</h3>
      <div style="space-y: 12px;">
        <div style="margin-bottom: 12px;">
          <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Contract ID</div>
          <div style="font-weight: 600; font-size: 15px; color: {THEME['text_primary']};">{contract_id}</div>
        </div>
        <div style="margin-bottom: 12px;">
          <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Service Type</div>
          <div style="font-size: 15px; color: {THEME['text_primary']};">{service_type}</div>
        </div>
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Start Date</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{start_date}</div></div>' if start_date else ''}
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Total</div><div style="font-weight: 600; font-size: 16px; color: {THEME["primary"]};">${total_value:,.2f}</div></div>' if total_value else ''}
      </div>
    </div>
    
    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
      <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
        🚀 Your signed contract PDF is attached. Schedule your first service anytime!
      </p>
    </div>
    
    <p style="color: {THEME['text_muted']}; font-size: 14px;">
      Questions? Reply here{f' or call {business_phone}' if business_phone else ''}.
    </p>
    <p style="margin-top: 20px;">Clean regards,<br/><strong>{business_name} Team</strong></p>
    """
    return await send_email(
        to=to,
        subject=f"Great News! Your Cleaning Contract is Fully Signed & Ready 🚀 [Contract {contract_id}]",
        title="Contract Fully Signed!",
        intro=f"{business_name} has reviewed and signed your service agreement.",
        content_html=content,
        cta_url=contract_pdf_url,
        cta_label="Download Signed Contract" if contract_pdf_url else None,
    )


async def send_provider_contract_signed_confirmation(
    to: str,
    provider_name: str,
    contract_id: int,
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
        <div style="font-weight: 600; font-size: 15px; color: {THEME['text_primary']};">{contract_id}</div>
      </div>
      <div style="margin-bottom: 12px;">
        <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Client</div>
        <div style="font-size: 15px; color: {THEME['text_primary']};">{client_name}</div>
      </div>
      {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Property</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{property_address}</div></div>' if property_address else ''}
    </div>
    
    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
      <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
        ✓ Proceed with scheduling
      </p>
    </div>
    
    <p style="color: {THEME['text_muted']}; font-size: 14px;">Signed PDF attached.</p>
    """
    return await send_email(
        to=to,
        subject=f"You've Signed Contract {contract_id} - Client Notification Sent",
        title="Contract Signed Successfully",
        intro="The contract has been fully executed.",
        content_html=content,
        cta_url=contract_pdf_url,
        cta_label="View Signed Contract" if contract_pdf_url else None,
    )


async def send_scheduling_proposal_email(
    client_email: str,
    client_name: str,
    provider_name: str,
    contract_id: int,
    time_slots: list,
    expires_at: str
) -> dict:
    """Send scheduling proposal to client with available time slots"""
    # Format time slots for display
    slots_html = ""
    for i, slot in enumerate(time_slots, 1):
        recommended = " <span style='color: #00C4B4; font-weight: 600;'>⭐ Recommended</span>" if slot.get('recommended') else ""
        slots_html += f"""
        <div style="background: {THEME['background']}; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
            <div style="font-weight: 600; color: {THEME['text_primary']}; margin-bottom: 4px;">Option {i}{recommended}</div>
            <div style="color: {THEME['text_muted']}; font-size: 14px;">
                📅 {slot.get('date')} | ⏰ {slot.get('start_time')} - {slot.get('end_time')}
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
            💡 Tip: Click the button below to select a time slot or suggest your own preferred times!
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
        cta_label="Select Time Slot"
    )


async def send_scheduling_accepted_email(
    provider_email: str,
    provider_name: str,
    client_name: str,
    contract_id: int,
    selected_date: str,
    start_time: str,
    end_time: str,
    property_address: Optional[str] = None
) -> dict:
    """Notify provider when client accepts a time slot"""
    content = f"""
    <p>Hi {provider_name},</p>
    <p>{client_name} has accepted a time slot for Contract {contract_id}:</p>
    
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Scheduled Date</div>
            <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">📅 {selected_date}</div>
        </div>
        <div style="margin-bottom: 12px;">
            <div style="color: {THEME['text_muted']}; font-size: 13px; margin-bottom: 4px;">Time</div>
            <div style="font-weight: 600; font-size: 16px; color: {THEME['text_primary']};">⏰ {start_time} - {end_time}</div>
        </div>
        {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Location</div><div style="font-size: 15px; color: {THEME["text_primary"]};">{property_address}</div></div>' if property_address else ''}
    </div>
    
    <div style="background: #dcfce7; border: 1px solid #22c55e; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-size: 14px; font-weight: 600;">
            ✓ Appointment confirmed
        </p>
    </div>
    """
    
    return await send_email(
        to=provider_email,
        subject=f"Time Slot Accepted for Contract {contract_id}",
        title="Scheduling Confirmed",
        intro=f"{client_name} has accepted your proposed time.",
        content_html=content
    )


async def send_scheduling_counter_proposal_email(
    provider_email: str,
    provider_name: str,
    client_name: str,
    contract_id: int,
    preferred_days: Optional[str] = None,
    time_window: Optional[str] = None,
    client_notes: Optional[str] = None
) -> dict:
    """Notify provider when client proposes alternative times"""
    content = f"""
    <p>Hi {provider_name},</p>
    <p>{client_name} has suggested alternative scheduling preferences for Contract {contract_id}:</p>
    
    <div style="background: {THEME['background']}; border-radius: 12px; padding: 20px; margin: 24px 0;">
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Preferred Days</div><div style="font-size: 15px; color: {THEME["text_primary"]};">📅 {preferred_days}</div></div>' if preferred_days else ''}
        {f'<div style="margin-bottom: 12px;"><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Time Window</div><div style="font-size: 15px; color: {THEME["text_primary"]};">⏰ {time_window}</div></div>' if time_window else ''}
        {f'<div><div style="color: {THEME["text_muted"]}; font-size: 13px; margin-bottom: 4px;">Client Notes</div><div style="font-size: 15px; color: {THEME["text_primary"]}; font-style: italic;">"{client_notes}"</div></div>' if client_notes else ''}
    </div>
    
    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
            ⏳ Counter-proposal received - Please review and respond
        </p>
    </div>
    """
    
    return await send_email(
        to=provider_email,
        subject=f"Alternative Times Proposed for Contract {contract_id}",
        title="Scheduling Counter-Proposal",
        intro=f"{client_name} has suggested different times.",
        content_html=content
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
            ⚠️ If you didn't request this code, you can safely ignore this email.
        </p>
    </div>
    """
    return await send_email(
        to=to,
        subject="Verify Your Email - CleanEnroll",
        title="Verify Your Email Address",
        intro="Please confirm your email to secure your account.",
        content_html=content,
    )
