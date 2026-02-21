"""
MJML Email Templates - Enterprise SaaS Standard
All email templates using MJML for responsive, cross-client compatibility
Following enterprise best practices with mobile-first design
"""

from typing import Optional

# App theme colors - Teal/Slate color scheme
THEME = {
    "primary": "#14b8a6",
    "primary_dark": "#0d9488",
    "primary_light": "#ccfbf1",
    "background": "#f8fafc",
    "card_bg": "#ffffff",
    "text_primary": "#0f172a",
    "text_secondary": "#334155",
    "text_muted": "#64748b",
    "border": "#e2e8f0",
    "success": "#14b8a6",
    "warning": "#f59e0b",
    "danger": "#ef4444",
}

LOGO_URL = "https://cleanenroll.com/CleaningAPP%20logo%20black%20new.png"


def get_base_template(
    title: str,
    preview_text: str,
    content_sections: str,
    cta_url: Optional[str] = None,
    cta_label: Optional[str] = None,
    is_user_email: bool = False,
) -> str:
    """
    Base MJML template wrapper for all emails
    Enterprise SaaS standard with mobile-first responsive design
    """

    cta_section = ""
    if cta_url and cta_label:
        cta_section = f"""
        <mj-section padding="24px 16px">
          <mj-column>
            <mj-button 
              href="{cta_url}" 
              background-color="{THEME['primary']}" 
              color="#ffffff"
              font-weight="600"
              border-radius="6px"
              padding="0"
              inner-padding="14px 32px"
              font-size="16px"
              width="100%">
              {cta_label}
            </mj-button>
          </mj-column>
        </mj-section>
        """

    footer_notice = ""
    if is_user_email:
        footer_notice = """
        <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="8px 0 0 0">
          You're receiving this because you have an account with CleanEnroll.
        </mj-text>
        """

    return f"""
    <mjml>
      <mj-head>
        <mj-title>{title}</mj-title>
        <mj-preview>{preview_text}</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
          <mj-section padding="24px 16px" />
        </mj-attributes>
        <mj-style>
          @media only screen and (max-width: 480px) {{
            .mobile-padding {{ padding: 16px !important; }}
            .mobile-heading {{ font-size: 24px !important; }}
          }}
        </mj-style>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
          
          <!-- Header with Logo -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px">
            <mj-column>
              <mj-image 
                src="{LOGO_URL}" 
                alt="CleanEnroll" 
                width="140px"
                href="https://cleanenroll.com"
                padding="0" />
            </mj-column>
          </mj-section>
          
          <!-- Divider -->
          <mj-section background-color="#ffffff" padding="0 24px">
            <mj-column>
              <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0" />
            </mj-column>
          </mj-section>

          <!-- Main Content -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px" css-class="mobile-padding">
            <mj-column>
              <mj-text 
                font-size="32px" 
                font-weight="600" 
                color="{THEME['text_primary']}" 
                line-height="1.3" 
                padding="0 0 16px 0"
                css-class="mobile-heading">
                {title}
              </mj-text>
              
              {content_sections}
            </mj-column>
          </mj-section>

          {cta_section}

        <!-- Footer -->
        <mj-section padding="32px 24px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" line-height="1.5" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            {footer_notice}
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def welcome_email_template(user_name: str) -> str:
    """Welcome email MJML template - Enterprise SaaS standard"""
    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      Your account has been created successfully.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {user_name},
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Welcome to CleanEnroll. We're excited to have you on board.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      With CleanEnroll, you can:
    </mj-text>
    
    <mj-text padding="0 0 4px 16px" line-height="1.6">
      Create professional client intake forms
    </mj-text>
    <mj-text padding="0 0 4px 16px" line-height="1.6">
      Generate contracts automatically
    </mj-text>
    <mj-text padding="0 0 16px 16px" line-height="1.6">
      Manage your cleaning business efficiently
    </mj-text>
    
    <mj-text padding="0" line-height="1.6">
      Get started by setting up your business profile and creating your first form.
    </mj-text>
    """

    return get_base_template(
        title="Welcome to CleanEnroll",
        preview_text="Your account has been created successfully",
        content_sections=content,
        cta_url="https://cleanenroll.com/dashboard",
        cta_label="Go to Dashboard",
        is_user_email=True,
    )


def email_verification_template(user_name: str, otp: str) -> str:
    """Email verification OTP MJML template - Enterprise SaaS standard"""
    return f"""
    <mjml>
      <mj-head>
        <mj-title>Verify Your Email Address</mj-title>
        <mj-preview>Your verification code is {otp}</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
        <mj-style>
          @media only screen and (max-width: 480px) {{
            .mobile-padding {{ padding: 16px !important; }}
            .mobile-heading {{ font-size: 24px !important; }}
            .mobile-otp {{ font-size: 28px !important; letter-spacing: 4px !important; }}
          }}
        </mj-style>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
          
          <!-- Header with Logo -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px">
            <mj-column>
              <mj-image 
                src="{LOGO_URL}" 
                alt="CleanEnroll" 
                width="140px"
                href="https://cleanenroll.com"
                padding="0" />
            </mj-column>
          </mj-section>
          
          <!-- Divider -->
          <mj-section background-color="#ffffff" padding="0 24px">
            <mj-column>
              <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0" />
            </mj-column>
          </mj-section>

          <!-- Main Content -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px" css-class="mobile-padding">
            <mj-column>
              <mj-text 
                font-size="32px" 
                font-weight="600" 
                color="{THEME['text_primary']}" 
                line-height="1.3" 
                padding="0 0 16px 0"
                css-class="mobile-heading">
                Verify Your Email Address
              </mj-text>
              
              <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
                Please confirm your email to secure your account.
              </mj-text>
              
              <mj-text padding="0 0 16px 0" line-height="1.6">
                Hi {user_name},
              </mj-text>
              
              <mj-text padding="0 0 24px 0" line-height="1.6">
                Please use the following verification code to confirm your email address. This code will expire in 10 minutes.
              </mj-text>
            </mj-column>
          </mj-section>
          
          <!-- OTP Card -->
          <mj-section background-color="#ffffff" padding="0 24px 24px 24px">
            <mj-column background-color="{THEME['primary_light']}" border-radius="6px">
                    <mj-text 
                      align="center" 
                      font-size="13px" 
                      color="{THEME['text_muted']}" 
                      text-transform="uppercase" 
                      letter-spacing="1px" 
                      font-weight="600" 
                      padding="24px 16px 12px 16px"
                      line-height="1.5">
                      Verification Code
                    </mj-text>
                    <mj-text 
                      align="center" 
                      font-size="36px" 
                      font-weight="700" 
                      color="{THEME['text_primary']}" 
                      letter-spacing="8px" 
                      font-family="'Courier New', monospace" 
                      padding="0 16px 24px 16px"
                      css-class="mobile-otp">
                      {otp}
                    </mj-text>
                  </mj-column>
          </mj-section>
          
          <mj-section background-color="#ffffff" padding="0 24px 32px 24px">
            <mj-column>
              <mj-text color="{THEME['text_muted']}" font-size="14px" padding="0" line-height="1.5">
                If you didn't request this code, you can safely ignore this email.
              </mj-text>
            </mj-column>
          </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 24px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" line-height="1.5" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="8px 0 0 0">
              You're receiving this because you have an account with CleanEnroll.
            </mj-text>
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def password_reset_template(reset_link: str) -> str:
    """Password reset MJML template - Enterprise SaaS standard"""
    return f"""
    <mjml>
      <mj-head>
        <mj-title>Reset Your Password</mj-title>
        <mj-preview>Reset your CleanEnroll password</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
        <mj-style>
          @media only screen and (max-width: 480px) {{
            .mobile-padding {{ padding: 16px !important; }}
            .mobile-heading {{ font-size: 24px !important; }}
          }}
        </mj-style>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
          
          <!-- Header with Logo -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px">
            <mj-column>
              <mj-image 
                src="{LOGO_URL}" 
                alt="CleanEnroll" 
                width="140px"
                href="https://cleanenroll.com"
                padding="0" />
            </mj-column>
          </mj-section>
          
          <!-- Divider -->
          <mj-section background-color="#ffffff" padding="0 24px">
            <mj-column>
              <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0" />
            </mj-column>
          </mj-section>

          <!-- Main Content -->
          <mj-section background-color="#ffffff" padding="32px 24px 24px 24px" css-class="mobile-padding">
            <mj-column>
              <mj-text 
                font-size="32px" 
                font-weight="600" 
                color="{THEME['text_primary']}" 
                line-height="1.3" 
                padding="0 0 16px 0"
                css-class="mobile-heading">
                Reset Your Password
              </mj-text>
              
              <mj-text padding="0 0 16px 0" line-height="1.6">
                We received a request to reset your password.
              </mj-text>
              
              <mj-text padding="0 0 24px 0" line-height="1.6">
                Click the button below to create a new password. This link will expire in 1 hour.
              </mj-text>
            </mj-column>
          </mj-section>
          
          <!-- Info Card -->
          <mj-section background-color="#ffffff" padding="0 24px 24px 24px">
            <mj-column>
              <mj-text font-size="14px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
                If you didn't request this, you can safely ignore this email. Your password won't be changed.
              </mj-text>
            </mj-column>
          </mj-section>
          
          <!-- CTA Button -->
          <mj-section background-color="#ffffff" padding="0 24px 32px 24px">
            <mj-column>
              <mj-button 
                href="{reset_link}" 
                background-color="{THEME['primary']}" 
                color="#ffffff"
                font-weight="600"
                border-radius="6px"
                padding="0"
                inner-padding="14px 32px"
                font-size="16px"
                width="100%">
                Reset Password
              </mj-button>
            </mj-column>
          </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 24px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" line-height="1.5" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" line-height="1.5" padding="8px 0 0 0">
              You're receiving this because you have an account with CleanEnroll.
            </mj-text>
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def new_client_notification_template(
    business_name: str,
    client_name: str,
    client_email: str,
    property_type: str,
    property_shots_count: int = 0,
) -> str:
    """New client submission notification MJML template - Enterprise SaaS standard"""

    property_shots_section = ""
    if property_shots_count > 0:
        property_shots_section = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Property photos attached as ZIP file: {property_shots_count} images
    </mj-text>
        """

    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      New {property_type} property intake: {client_name} ready to review
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {business_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      {client_name} ({client_email}) completed a {property_type} cleaning intake form for {business_name}.
    </mj-text>
    
    {property_shots_section}
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="15px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 12px 0" line-height="1.5">
          Key Details Captured
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_muted']}" padding="0 0 4px 0" line-height="1.5">
          Property type: {property_type}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
          Full intake details available in dashboard (sq ft, peak hours, security codes, fragile displays)
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="15px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 12px 0" line-height="1.5">
          Next Steps
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.6">
          Review property specifics in dashboard, then wait for auto-generated contract to be reviewed and signed by client.
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Best,
    </mj-text>
    <mj-text padding="0" font-weight="600" line-height="1.6">
      CleanEnroll Team
    </mj-text>
    """

    return get_base_template(
        title="New Client Property Intake Submission",
        preview_text=f"New {property_type} Property Intake: {client_name} Ready to Review",
        content_sections=content,
        cta_url="https://cleanenroll.com/dashboard",
        cta_label="View Dashboard",
        is_user_email=True,
    )


def form_submission_confirmation_template(
    client_name: str,
    business_name: str,
    property_type: str = "Property",
) -> str:
    """Form submission confirmation MJML template - Enterprise SaaS standard"""
    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      Thank you for completing your {property_type} cleaning intake
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Thank you for completing your {property_type} cleaning intake form for {business_name}.
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Your property details (square footage, peak hours, security codes, fragile displays) and proposed schedule have been received and processed successfully.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="15px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 12px 0" line-height="1.5">
          What's Next
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0" line-height="1.6">
          Auto-generated contract with dynamic pricing sent to your email
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0" line-height="1.6">
          Review and sign at your convenience
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.6">
          {business_name} will review your proposed schedule and confirm
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="24px 0 0 0" line-height="1.5">
      Questions? Contact {business_name} directly.
    </mj-text>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Best,
    </mj-text>
    <mj-text padding="0" font-weight="600" line-height="1.6">
      CleanEnroll
    </mj-text>
    """

    return get_base_template(
        title=f"Thank You for Your {property_type} Cleaning Intake",
        preview_text=f"Thank you for completing your {property_type} cleaning intake",
        content_sections=content,
    )


def contract_signed_notification_template(
    business_name: str, client_name: str, contract_title: str
) -> str:
    """Contract signed by client notification MJML template - Enterprise SaaS standard"""
    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      A contract for {business_name} requires your signature.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Great news! {client_name} has signed their contract.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Contract: {contract_title}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Client: {client_name}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Status: Awaiting Your Signature
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      The contract is now awaiting your signature to be fully executed. Review the client's proposed schedule and sign to complete the agreement.
    </mj-text>
    """

    return get_base_template(
        title="Client Has Signed",
        preview_text=f"Contract Signed by {client_name} - Review Schedule & Sign",
        content_sections=content,
        cta_url="https://cleanenroll.com/contracts",
        cta_label="Review & Sign Contract",
        is_user_email=True,
    )


def client_signature_confirmation_template(
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_pdf_url: Optional[str] = None,
) -> str:
    """Client signature confirmation MJML template - Enterprise SaaS standard"""
    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      Your contract with {business_name} has been signed successfully.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Thank you for signing your contract with {business_name}.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Contract: {contract_title}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Status: Awaiting Provider Signature
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Your signature has been recorded successfully. The service provider will review and sign the contract shortly.
    </mj-text>
    """

    cta_url = contract_pdf_url if contract_pdf_url else None
    cta_label = "View Signed Contract" if contract_pdf_url else None

    return get_base_template(
        title="Thank You for Signing",
        preview_text=f"Contract Signed - Awaiting {business_name}",
        content_sections=content,
        cta_url=cta_url,
        cta_label=cta_label,
    )


def contract_fully_executed_template(
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
) -> str:
    """Contract fully executed notification MJML template - Enterprise SaaS standard"""

    total_section = ""
    if total_value:
        total_section = f"""
          <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
            Total: ${total_value:,.2f}
          </mj-text>
        """

    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      {business_name} has reviewed and signed your service agreement.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Perfect! {business_name} has reviewed and signed your service agreement{f' for {property_address}' if property_address else ''}.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Contract ID: {contract_id}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Service Type: {service_type}
        </mj-text>
        {total_section}
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Your signed contract PDF is attached. Your schedule has been confirmed.
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="16px 0 0 0" line-height="1.5">
      Questions? Reply here{f' or call {business_phone}' if business_phone else ''}.
    </mj-text>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Clean regards,
    </mj-text>
    <mj-text padding="0" font-weight="600" line-height="1.6">
      {business_name} Team
    </mj-text>
    """

    return get_base_template(
        title="Contract Fully Signed",
        preview_text=f"Great News! Your Cleaning Contract is Fully Signed & Ready [Contract {contract_id}]",
        content_sections=content,
        cta_url=contract_pdf_url,
        cta_label="Download Signed Contract" if contract_pdf_url else None,
    )


def quote_submitted_confirmation_template(
    client_name: str,
    business_name: str,
    quote_amount: float,
) -> str:
    """Quote submission confirmation MJML template - Enterprise SaaS standard"""
    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      Thank you for your interest in {business_name}'s services.
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Thank you for submitting your quote request. We've received your approval and {business_name} will review it shortly.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['text_primary']}" padding="0 0 8px 0" line-height="1.2">
          ${quote_amount:,.2f}
        </mj-text>
        <mj-text align="center" font-size="14px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
          This is an automated estimate. Final pricing will be confirmed by {business_name}.
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="24px 0 0 0" line-height="1.5">
      Expected response time: Within minutes to hours
    </mj-text>
    """

    return get_base_template(
        title="Quote Request Submitted",
        preview_text=f"Your Quote Request Has Been Submitted - {business_name}",
        content_sections=content,
    )


def quote_review_notification_template(
    provider_name: str,
    client_name: str,
    client_email: str,
    quote_amount: float,
    client_public_id: str,
) -> str:
    """Quote review notification for provider MJML template - Enterprise SaaS standard"""
    review_link = f"https://cleanenroll.com/dashboard/quote-requests/{client_public_id}"

    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {provider_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      {client_name} has approved an automated quote and is waiting for your review.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Name: {client_name}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Email: {client_email}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Automated Quote: ${quote_amount:,.2f}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="24px 0 0 0" line-height="1.5">
      Recommended response time: Within minutes to hours
    </mj-text>
    """

    return get_base_template(
        title="New Quote Approval Request",
        preview_text=f"New Quote Approval Request from {client_name}",
        content_sections=content,
        cta_url=review_link,
        cta_label="Review & Approve Quote",
        is_user_email=True,
    )


def quote_approved_template(
    client_name: str,
    business_name: str,
    final_quote_amount: float,
    was_adjusted: bool,
    adjustment_notes: str = None,
    client_public_id: str = None,
) -> str:
    """Quote approved notification MJML template - Enterprise SaaS standard"""
    scope_of_work_link = f"https://cleanenroll.com/client-schedule/{client_public_id}"

    adjustment_section = ""
    if was_adjusted and adjustment_notes:
        adjustment_section = f"""
    <mj-section background-color="#fef3c7" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" font-weight="600" color="#92400e" padding="0 0 8px 0" line-height="1.5">
          Quote Adjusted
        </mj-text>
        <mj-text font-size="14px" color="#92400e" padding="0" line-height="1.5">
          {adjustment_notes}
        </mj-text>
      </mj-column>
    </mj-section>
        """

    subject = "Your Quote Has Been Updated" if was_adjusted else "Your Quote Has Been Approved"

    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Great news! {business_name} has reviewed and approved your quote. The next step is to define your specific cleaning needs.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="36px" font-weight="700" color="{THEME['text_primary']}" padding="0" line-height="1.2">
          ${final_quote_amount:,.2f}
        </mj-text>
      </mj-column>
    </mj-section>
    
    {adjustment_section}
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Click the button below to build your Scope of Work, review the service agreement, and complete your booking.
    </mj-text>
    """

    return get_base_template(
        title=subject,
        preview_text=f"{subject} - {business_name}",
        content_sections=content,
        cta_url=scope_of_work_link,
        cta_label="Build Your Scope of Work",
    )


def payment_received_notification_template(
    provider_name: str,
    client_name: str,
    invoice_number: str,
    amount: float,
    currency: str = "USD",
    payment_date: Optional[str] = None,
) -> str:
    """Payment received notification MJML template - Enterprise SaaS standard"""

    payment_date_section = ""
    if payment_date:
        payment_date_section = f"""
          <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
            Payment Date: {payment_date}
          </mj-text>
        """

    content = f"""
    <mj-text color="{THEME['text_secondary']}" padding="0 0 24px 0" line-height="1.6">
      Great news! {client_name} has paid invoice {invoice_number}.
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Hi {provider_name},
    </mj-text>
    
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Excellent news! {client_name} has just paid their invoice.
    </mj-text>
    
    <mj-section background-color="{THEME['primary_light']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="32px" color="{THEME['primary']}" font-weight="700" padding="0 0 8px 0" line-height="1.2">
          ${amount:,.2f} {currency}
        </mj-text>
        <mj-text align="center" color="{THEME['primary_dark']}" font-size="16px" font-weight="600" padding="0" line-height="1.5">
          Payment Received
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Invoice: {invoice_number}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Client: {client_name}
        </mj-text>
        {payment_date_section}
      </mj-column>
    </mj-section>
    
    <mj-section background-color="#fef3c7" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" font-weight="600" color="#92400e" padding="0 0 8px 0" line-height="1.5">
          Ready for Payout
        </mj-text>
        <mj-text font-size="14px" color="#92400e" padding="0" line-height="1.5">
          This payment has been added to your available balance and is ready for withdrawal.
        </mj-text>
      </mj-column>
    </mj-section>
    """

    return get_base_template(
        title="Payment Received",
        preview_text=f"Payment Received: ${amount:,.2f} from {client_name}",
        content_sections=content,
        cta_url="https://cleanenroll.com/dashboard/payouts",
        cta_label="View Payouts Dashboard",
        is_user_email=True,
    )


def contract_fully_executed_schedule_invitation_template(
    client_name: str,
    business_name: str,
    contract_title: str,
    contract_id: str,
    client_public_id: str,
) -> str:
    """Email template inviting client to schedule after both parties sign the MSA - Enterprise SaaS standard"""

    schedule_link = f"https://cleanenroll.com/client-schedule/{client_public_id}"

    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Congratulations! Your service agreement with {business_name} is now fully executed and ready to go.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Contract: {contract_title}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Contract ID: {contract_id}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      The next step is to schedule your first cleaning session. Click the button below to choose your preferred date and time.
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="16px 0 0 0" line-height="1.5">
      You'll be able to select from available time slots or propose alternative times that work better for your schedule.
    </mj-text>
    """

    return get_base_template(
        title="Schedule Your First Cleaning",
        preview_text=f"Your agreement with {business_name} is ready - Schedule your first cleaning",
        content_sections=content,
        cta_url=schedule_link,
        cta_label="Schedule Your First Cleaning",
    )


def schedule_confirmed_client_template(
    client_name: str,
    business_name: str,
    scheduled_date: str,
    scheduled_time: str,
) -> str:
    """Schedule confirmed notification for client - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Great news! {business_name} has confirmed your preferred cleaning schedule.
    </mj-text>
    
    <mj-section background-color="{THEME['primary_light']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="16px" font-weight="600" color="{THEME['success']}" padding="0 0 16px 0" line-height="1.5">
          Confirmed Cleaning Date & Time
        </mj-text>
        <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          {scheduled_date}
        </mj-text>
        <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          {scheduled_time}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Your first cleaning is all set. We look forward to serving you.
    </mj-text>
    """

    return get_base_template(
        title="Your Cleaning is Scheduled",
        preview_text=f"Cleaning Schedule Confirmed - {business_name}",
        content_sections=content,
    )


def schedule_confirmed_provider_template(
    provider_name: str,
    client_name: str,
    scheduled_date: str,
    scheduled_time: str,
) -> str:
    """Schedule confirmed notification for provider - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {provider_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      You confirmed a cleaning schedule for {client_name}.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          {scheduled_date} {scheduled_time}
        </mj-text>
      </mj-column>
    </mj-section>
    """

    return get_base_template(
        title="Schedule Confirmed",
        preview_text=f"Schedule Confirmed for {client_name}",
        content_sections=content,
        is_user_email=True,
    )


def alternative_time_proposed_client_template(
    client_name: str,
    business_name: str,
    proposed_date: str,
    proposed_time: str,
) -> str:
    """Alternative time proposed notification for client - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      {business_name} has proposed an alternative cleaning time for your convenience.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="16px" color="{THEME['primary']}" font-weight="600" padding="0 0 16px 0" line-height="1.5">
          Proposed Alternative Time
        </mj-text>
        <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          {proposed_date}
        </mj-text>
        <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          {proposed_time}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      The service provider will reach out to you shortly to confirm this new time or discuss other options that work for both of you.
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="16px 0 0 0" line-height="1.5">
      If you have any questions or concerns, please contact {business_name} directly.
    </mj-text>
    """

    return get_base_template(
        title="Schedule Change Request",
        preview_text=f"Alternative Cleaning Time Proposed - {business_name}",
        content_sections=content,
    )


def alternative_time_proposed_provider_template(
    provider_name: str,
    client_name: str,
    proposed_date: str,
    proposed_time: str,
) -> str:
    """Alternative time proposed confirmation for provider - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {provider_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      You proposed an alternative time for {client_name}.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Proposed: {proposed_date} {proposed_time}
        </mj-text>
      </mj-column>
    </mj-section>
    """

    return get_base_template(
        title="Alternative Time Proposed",
        preview_text=f"Alternative Time Sent to {client_name}",
        content_sections=content,
        is_user_email=True,
    )


def new_schedule_request_template(
    provider_name: str,
    client_name: str,
    scheduled_date: str,
    scheduled_time: str,
    duration_minutes: int,
    client_email: str = "",
    client_phone: str = "",
    dashboard_url: str = "https://cleanenroll.com/schedule",
) -> str:
    """New schedule request notification for provider - Enterprise SaaS standard"""
    contact_info = ""
    if client_email or client_phone:
        contact_lines = []
        if client_email:
            contact_lines.append(f"Email: {client_email}")
        if client_phone:
            contact_lines.append(f"Phone: {client_phone}")

        contact_info = f"""
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Client: {client_name}
        </mj-text>
        {"".join([f'<mj-text font-size="14px" color="{THEME["text_primary"]}" padding="0 0 4px 0" line-height="1.5">{line}</mj-text>' for line in contact_lines])}
      </mj-column>
    </mj-section>
        """

    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {provider_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      {client_name} has selected their preferred cleaning time.
    </mj-text>
    
    <mj-section background-color="{THEME['primary_light']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="15px" font-weight="600" color="{THEME['primary']}" padding="0 0 12px 0" line-height="1.5">
          Requested Cleaning Schedule
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Date: {scheduled_date}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Time: {scheduled_time}
        </mj-text>
        <mj-text font-size="13px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
          Duration: {duration_minutes} minutes
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-section background-color="#fef3c7" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" font-weight="600" color="#92400e" padding="0 0 8px 0" line-height="1.5">
          Action Required
        </mj-text>
        <mj-text font-size="14px" color="#92400e" padding="0" line-height="1.5">
          Please review and confirm this schedule in your dashboard, or propose an alternative time if needed.
        </mj-text>
      </mj-column>
    </mj-section>
    
    {contact_info}
    """

    return get_base_template(
        title="Client Selected Cleaning Time",
        preview_text=f"New Schedule Request from {client_name}",
        content_sections=content,
        cta_url=dashboard_url,
        cta_label="Review Schedule",
        is_user_email=True,
    )


def payment_confirmation_client_template(
    client_name: str,
    business_name: str,
    amount: float,
    contract_title: str,
    payment_date: str,
) -> str:
    """Payment confirmation for client - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Thank you! Your payment for {contract_title} has been successfully processed.
    </mj-text>
    
    <mj-section background-color="{THEME['primary_light']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="36px" font-weight="700" color="{THEME['success']}" padding="0 0 8px 0" line-height="1.2">
          ${amount:,.2f}
        </mj-text>
        <mj-text align="center" color="{THEME['primary_dark']}" font-size="16px" font-weight="600" padding="0" line-height="1.5">
          Payment Received
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Payment Date: {payment_date}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Service: {contract_title}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Provider: {business_name}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text font-size="13px" color="{THEME['text_muted']}" padding="24px 0 0 0" line-height="1.5">
      This is an automated confirmation email. Please do not reply to this message.
    </mj-text>
    """

    return get_base_template(
        title="Payment Received",
        preview_text=f"Payment Received - {contract_title}",
        content_sections=content,
    )


def subscription_activated_template(
    client_name: str,
    business_name: str,
    frequency: str,
    contract_title: str,
    amount: float,
) -> str:
    """Subscription activated notification for client - Enterprise SaaS standard"""
    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Great news! Your {frequency} subscription for {contract_title} is now active.
    </mj-text>
    
    <mj-section background-color="{THEME['primary_light']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['success']}" padding="0 0 8px 0" line-height="1.2">
          ${amount:,.2f}
        </mj-text>
        <mj-text align="center" font-size="16px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
          per {frequency}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      Your card will be automatically charged on the scheduled date. You'll receive a confirmation email after each payment.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="16px 0 0 0" line-height="1.5">
      Service Provider: {business_name}
    </mj-text>
    """

    return get_base_template(
        title="Subscription Activated",
        preview_text=f"Subscription Activated - {frequency.title()} {contract_title}",
        content_sections=content,
    )


def invoice_ready_template(
    client_name: str,
    business_name: str,
    invoice_number: str,
    amount: float,
    due_date: str = "",
    payment_url: str = "",
    is_deposit: bool = False,
    deposit_percentage: int = 50,
    remaining_balance: Optional[float] = None,
) -> str:
    """
    Invoice ready notification for client - Enterprise SaaS standard

    Args:
        is_deposit: If True, shows deposit information
        deposit_percentage: Percentage of deposit
        remaining_balance: Remaining balance after deposit
    """
    due_date_section = ""
    if due_date:
        due_date_section = f"""
          <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
            Due Date: {due_date}
          </mj-text>
        """

    # Deposit-specific messaging
    deposit_info = ""
    if is_deposit and remaining_balance:
        total_job_amount = amount + remaining_balance
        deposit_info = f"""
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 12px 0" line-height="1.5">
          Payment Structure
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Total Job Amount: ${total_job_amount:,.2f}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Deposit ({deposit_percentage}%): ${amount:,.2f}
        </mj-text>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0" line-height="1.5">
          Balance Due After Completion: ${remaining_balance:,.2f}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-text padding="24px 0 0 0" line-height="1.6">
      This {deposit_percentage}% deposit secures your service appointment. The remaining balance of ${remaining_balance:,.2f} will be invoiced after your service is completed.
    </mj-text>
        """
    elif is_deposit:
        deposit_info = f"""
    <mj-text padding="24px 0 0 0" line-height="1.6">
      This is a {deposit_percentage}% deposit to secure your service appointment. The remaining balance will be invoiced after your service is completed.
    </mj-text>
        """

    content = f"""
    <mj-text padding="0 0 16px 0" line-height="1.6">
      Hi {client_name},
    </mj-text>
    
    <mj-text padding="0 0 24px 0" line-height="1.6">
      Your {'deposit ' if is_deposit else ''}invoice from {business_name} is ready for payment.
    </mj-text>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="24px 16px">
      <mj-column>
        <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['text_primary']}" padding="0 0 8px 0" line-height="1.2">
          ${amount:,.2f}
        </mj-text>
        <mj-text align="center" font-size="14px" color="{THEME['text_muted']}" padding="0" line-height="1.5">
          Invoice: {invoice_number}
        </mj-text>
      </mj-column>
    </mj-section>
    
    <mj-section background-color="{THEME['background']}" border-radius="6px" padding="16px">
      <mj-column>
        <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 4px 0" line-height="1.5">
          Invoice: {invoice_number}
        </mj-text>
        {due_date_section}
      </mj-column>
    </mj-section>
    
    {deposit_info}
    """

    cta_label = "Pay Deposit" if is_deposit else "Pay Invoice"

    return get_base_template(
        title=f"{'Deposit ' if is_deposit else ''}Invoice Ready",
        preview_text=f"{'Deposit ' if is_deposit else ''}Invoice Ready - {invoice_number}",
        content_sections=content,
        cta_url=payment_url if payment_url else None,
        cta_label=cta_label if payment_url else None,
    )


# Export all template functions
__all__ = [
    "get_base_template",
    "welcome_email_template",
    "email_verification_template",
    "password_reset_template",
    "new_client_notification_template",
    "form_submission_confirmation_template",
    "contract_signed_notification_template",
    "client_signature_confirmation_template",
    "contract_fully_executed_template",
    "contract_fully_executed_schedule_invitation_template",
    "quote_submitted_confirmation_template",
    "quote_review_notification_template",
    "quote_approved_template",
    "payment_received_notification_template",
    "schedule_confirmed_client_template",
    "schedule_confirmed_provider_template",
    "alternative_time_proposed_client_template",
    "alternative_time_proposed_provider_template",
    "new_schedule_request_template",
    "payment_confirmation_client_template",
    "subscription_activated_template",
    "invoice_ready_template",
    "THEME",
    "LOGO_URL",
]
