"""
MJML Email Templates
All email templates using MJML for responsive, cross-client compatibility
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
    """Base MJML template wrapper for all emails"""

    cta_section = ""
    if cta_url and cta_label:
        cta_section = f"""
        <mj-section padding="20px 0">
          <mj-column>
            <mj-button 
              href="{cta_url}" 
              background-color="{THEME['primary']}" 
              color="#ffffff"
              font-weight="600"
              border-radius="8px"
              padding="18px 40px"
              font-size="16px">
              {cta_label}
            </mj-button>
          </mj-column>
        </mj-section>
        """

    footer_notice = ""
    if is_user_email:
        footer_notice = """
        <mj-text align="center" font-size="12px" color="#94a3b8" padding="12px 0 0 0">
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
        </mj-attributes>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
        <!-- Header with Logo -->
        <mj-section background-color="#ffffff" padding="32px 20px">
          <mj-column>
            <mj-image 
              src="{LOGO_URL}" 
              alt="CleanEnroll" 
              width="140px"
              href="https://cleanenroll.com"
              padding="0" />
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="0 40px 40px 40px">
          <mj-column>
            <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0 0 32px 0" />
          </mj-column>
        </mj-section>

        <!-- Main Content -->
        <mj-section background-color="#ffffff" padding="0 40px 48px 40px">
          <mj-column>
            <mj-text font-size="24px" font-weight="600" color="{THEME['text_primary']}" line-height="1.3" padding="0 0 16px 0">
              {title}
            </mj-text>
            
            {content_sections}
          </mj-column>
        </mj-section>

        {cta_section}

        <!-- Footer -->
        <mj-section padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            {footer_notice}
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def welcome_email_template(user_name: str) -> str:
    """Welcome email MJML template"""
    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      Your account has been created successfully.
    </mj-text>
    
    <mj-text>
      Hi {user_name},
    </mj-text>
    
    <mj-text>
      Welcome to CleanEnroll! We're excited to have you on board.
    </mj-text>
    
    <mj-text>
      With CleanEnroll, you can:
    </mj-text>
    
    <mj-text padding="0 0 0 20px">
      • Create professional client intake forms<br/>
      • Generate contracts automatically<br/>
      • Manage your cleaning business efficiently
    </mj-text>
    
    <mj-text>
      Get started by setting up your business profile and creating your first form.
    </mj-text>
    """

    return get_base_template(
        title="Welcome to CleanEnroll!",
        preview_text="Your account has been created successfully",
        content_sections=content,
        cta_url="https://cleanenroll.com/dashboard",
        cta_label="Go to Dashboard",
        is_user_email=True,
    )


def email_verification_template(user_name: str, otp: str) -> str:
    """Email verification OTP MJML template"""
    # Build complete MJML without using nested sections
    return f"""
    <mjml>
      <mj-head>
        <mj-title>Verify Your Email Address</mj-title>
        <mj-preview>Your verification code is {otp}</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
        <!-- Header with Logo -->
        <mj-section background-color="#ffffff" padding="32px 20px">
          <mj-column>
            <mj-image 
              src="{LOGO_URL}" 
              alt="CleanEnroll" 
              width="140px"
              href="https://cleanenroll.com"
              padding="0" />
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="0 40px 40px 40px">
          <mj-column>
            <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0 0 32px 0" />
          </mj-column>
        </mj-section>

        <!-- Main Content -->
        <mj-section background-color="#ffffff" padding="0 40px 20px 40px">
          <mj-column>
            <mj-text font-size="24px" font-weight="600" color="{THEME['text_primary']}" line-height="1.3" padding="0 0 16px 0">
              Verify Your Email Address
            </mj-text>
            
            <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
              Please confirm your email to secure your account.
            </mj-text>
            
            <mj-text>
              Hi {user_name},
            </mj-text>
            
            <mj-text>
              Please use the following verification code to confirm your email address. This code will expire in 10 minutes.
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- OTP Section -->
        <mj-section background-color="{THEME['primary_light']}" padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="{THEME['text_muted']}" text-transform="uppercase" letter-spacing="1px" font-weight="600" padding="0 0 12px 0">
              Verification Code
            </mj-text>
            <mj-text align="center" font-size="36px" font-weight="700" color="{THEME['text_primary']}" letter-spacing="8px" font-family="'Courier New', monospace" padding="0">
              {otp}
            </mj-text>
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="20px 40px 48px 40px">
          <mj-column>
            <mj-text color="{THEME['text_muted']}" font-size="14px" padding="0">
              If you didn't request this code, you can safely ignore this email.
            </mj-text>
          </mj-column>
        </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            <mj-text align="center" font-size="12px" color="#94a3b8" padding="12px 0 0 0">
              You're receiving this because you have an account with CleanEnroll.
            </mj-text>
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def password_reset_template(reset_link: str) -> str:
    """Password reset MJML template"""
    return f"""
    <mjml>
      <mj-head>
        <mj-title>Reset Your Password</mj-title>
        <mj-preview>Reset your CleanEnroll password</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
        <!-- Header with Logo -->
        <mj-section background-color="#ffffff" padding="32px 20px">
          <mj-column>
            <mj-image 
              src="{LOGO_URL}" 
              alt="CleanEnroll" 
              width="140px"
              href="https://cleanenroll.com"
              padding="0" />
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="0 40px 40px 40px">
          <mj-column>
            <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0 0 32px 0" />
          </mj-column>
        </mj-section>

        <!-- Main Content -->
        <mj-section background-color="#ffffff" padding="0 40px 20px 40px">
          <mj-column>
            <mj-text font-size="24px" font-weight="600" color="{THEME['text_primary']}" line-height="1.3" padding="0 0 16px 0">
              Reset Your Password
            </mj-text>
            
            <mj-text>
              We received a request to reset your password.
            </mj-text>
            
            <mj-text>
              Click the button below to create a new password. This link will expire in 1 hour.
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- Info Box -->
        <mj-section background-color="{THEME['background']}" padding="16px 40px">
          <mj-column>
            <mj-text font-size="13px" color="{THEME['text_muted']}" padding="0">
              If you didn't request this, you can safely ignore this email. Your password won't be changed.
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- CTA Button -->
        <mj-section background-color="#ffffff" padding="20px 40px 48px 40px">
          <mj-column>
            <mj-button 
              href="{reset_link}" 
              background-color="{THEME['primary']}" 
              color="#ffffff"
              font-weight="600"
              border-radius="8px"
              padding="18px 40px"
              font-size="16px">
              Reset Password
            </mj-button>
          </mj-column>
        </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            <mj-text align="center" font-size="12px" color="#94a3b8" padding="12px 0 0 0">
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
    """New client submission notification MJML template"""

    property_shots_section = ""
    if property_shots_count > 0:
        property_shots_section = f"""
        <mj-section background-color="{THEME['primary_light']}" padding="16px 40px">
          <mj-column>
            <mj-text color="{THEME['primary_dark']}" font-size="14px" font-weight="600" padding="0">
              📷 Property photos attached as ZIP file ({property_shots_count} images)
            </mj-text>
          </mj-column>
        </mj-section>
        """

    return f"""
    <mjml>
      <mj-head>
        <mj-title>New Client Property Intake Submission</mj-title>
        <mj-preview>New {property_type} Property Intake: {client_name} Ready to Review</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
        <!-- Header with Logo -->
        <mj-section background-color="#ffffff" padding="32px 20px">
          <mj-column>
            <mj-image 
              src="{LOGO_URL}" 
              alt="CleanEnroll" 
              width="140px"
              href="https://cleanenroll.com"
              padding="0" />
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="0 40px 40px 40px">
          <mj-column>
            <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0 0 32px 0" />
          </mj-column>
        </mj-section>

        <!-- Main Content -->
        <mj-section background-color="#ffffff" padding="0 40px 20px 40px">
          <mj-column>
            <mj-text font-size="24px" font-weight="600" color="{THEME['text_primary']}" line-height="1.3" padding="0 0 16px 0">
              New Client Property Intake Submission
            </mj-text>
            
            <mj-text>
              Hi {business_name},
            </mj-text>
            
            <mj-text>
              {client_name} ({client_email}) completed a {property_type} cleaning intake form for {business_name}.
            </mj-text>
          </mj-column>
        </mj-section>
        
        {property_shots_section}
        
        <!-- Key Details -->
        <mj-section background-color="{THEME['background']}" padding="20px 40px">
          <mj-column>
            <mj-text font-size="16px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 16px 0">
              🏢 Key Details Captured:
            </mj-text>
            <mj-text color="{THEME['text_muted']}" font-size="13px" padding="0 0 4px 0">
              Property type: {property_type}
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_muted']}" padding="0">
              Full intake details available in dashboard (sq ft, peak hours, security codes, fragile displays)
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- Next Steps -->
        <mj-section background-color="{THEME['background']}" padding="20px 40px">
          <mj-column>
            <mj-text font-size="16px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 12px 0">
              ✨ Next Steps:
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0">
              Review property specifics in dashboard → Wait for auto-generated contract to be reviewed and signed by client
            </mj-text>
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="20px 40px 48px 40px">
          <mj-column>
            <mj-text font-size="15px" color="{THEME['text_primary']}" font-weight="600">
              First booking awaits! ✓
            </mj-text>
            
            <mj-text padding="20px 0 0 0">
              Best,<br/><strong>Cleanenroll Team</strong>
            </mj-text>
          </mj-column>
        </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
            <mj-text align="center" font-size="12px" color="#94a3b8" padding="12px 0 0 0">
              You're receiving this because you have an account with CleanEnroll.
            </mj-text>
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


def form_submission_confirmation_template(
    client_name: str,
    business_name: str,
    property_type: str = "Property",
) -> str:
    """Form submission confirmation MJML template"""
    return f"""
    <mjml>
      <mj-head>
        <mj-title>Thank You for Your {property_type} Cleaning Intake</mj-title>
        <mj-preview>Thank you for completing your {property_type} cleaning intake</mj-preview>
        <mj-attributes>
          <mj-all font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif" />
          <mj-text font-size="16px" line-height="1.6" color="{THEME['text_secondary']}" />
        </mj-attributes>
      </mj-head>
      <mj-body background-color="{THEME['background']}">
        <!-- Header with Logo -->
        <mj-section background-color="#ffffff" padding="32px 20px">
          <mj-column>
            <mj-image 
              src="{LOGO_URL}" 
              alt="CleanEnroll" 
              width="140px"
              href="https://cleanenroll.com"
              padding="0" />
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="0 40px 40px 40px">
          <mj-column>
            <mj-divider border-color="{THEME['border']}" border-width="1px" padding="0 0 32px 0" />
          </mj-column>
        </mj-section>

        <!-- Main Content -->
        <mj-section background-color="#ffffff" padding="0 40px 20px 40px">
          <mj-column>
            <mj-text font-size="24px" font-weight="600" color="{THEME['text_primary']}" line-height="1.3" padding="0 0 16px 0">
              Thank You for Your {property_type} Cleaning Intake
            </mj-text>
            
            <mj-text>
              Hi {client_name},
            </mj-text>
            
            <mj-text>
              Thank you for completing your {property_type} cleaning intake form for {business_name}!
            </mj-text>
            
            <mj-text>
              Your property details (square footage, peak hours, security codes, fragile displays) and proposed schedule have been received and processed successfully.
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- What's Next -->
        <mj-section background-color="{THEME['background']}" padding="20px 40px">
          <mj-column>
            <mj-text font-size="16px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 16px 0">
              What's Next:
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0">
              ✓ Auto-generated contract with dynamic pricing sent to your email
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0">
              ✓ Review & sign at your convenience
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0">
              ✓ {business_name} will review your proposed schedule and confirm
            </mj-text>
          </mj-column>
        </mj-section>
        
        <!-- Quick Confirmation -->
        <mj-section background-color="{THEME['background']}" padding="20px 40px">
          <mj-column>
            <mj-text font-size="16px" font-weight="600" color="{THEME['text_primary']}" padding="0 0 16px 0">
              Quick Confirmation:
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0">
              ✓ {property_type} property intake completed
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0 0 8px 0">
              ✓ Proposed schedule submitted
            </mj-text>
            <mj-text font-size="14px" color="{THEME['text_primary']}" padding="0">
              ✓ Ready for your review
            </mj-text>
          </mj-column>
        </mj-section>
        
        <mj-section background-color="#ffffff" padding="20px 40px 48px 40px">
          <mj-column>
            <mj-text color="{THEME['text_muted']}" font-size="14px">
              Questions? Contact {business_name} directly. Excited to get your store sparkling! ✨
            </mj-text>
            
            <mj-text padding="20px 0 0 0">
              Best,<br/><strong>Cleanenroll</strong>
            </mj-text>
          </mj-column>
        </mj-section>

        <!-- Footer -->
        <mj-section padding="32px 20px">
          <mj-column>
            <mj-text align="center" font-size="14px" color="#94a3b8" padding="0">
              <a href="https://cleanenroll.com/legal#privacy-policy" style="color: #64748b; text-decoration: none;">Privacy Policy</a>
              <span style="color: #cbd5e1; margin: 0 8px;">•</span>
              <a href="https://cleanenroll.com/legal#terms-of-service" style="color: #64748b; text-decoration: none;">Terms of Service</a>
            </mj-text>
            <mj-text align="center" font-size="13px" color="#94a3b8" padding="12px 0 0 0">
              © 2024 CleanEnroll. All rights reserved.
            </mj-text>
          </mj-column>
        </mj-section>
      </mj-body>
    </mjml>
    """


# Simplified templates for remaining functions
def contract_signed_notification_template(
    business_name: str, client_name: str, contract_title: str
) -> str:
    """Contract signed by client notification MJML template"""
    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      A contract for {business_name} requires your signature.
    </mj-text>
    
    <mj-text>
      Great news! <strong>{client_name}</strong> has signed their contract.
    </mj-text>
    
    <mj-text>
      Contract: {contract_title}<br/>
      Client: {client_name}<br/>
      Status: ⏰ Awaiting Your Signature
    </mj-text>
    
    <mj-text>
      The contract is now awaiting your signature to be fully executed. Review the client's proposed schedule and sign to complete the agreement.
    </mj-text>
    """

    return get_base_template(
        title="Client Has Signed!",
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
    """Client signature confirmation MJML template"""
    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      Your contract with {business_name} has been signed successfully.
    </mj-text>
    
    <mj-text>
      Thank you for signing your contract with <strong>{business_name}</strong>!
    </mj-text>
    
    <mj-text>
      Contract: {contract_title}<br/>
      Status: ⏰ Awaiting Provider Signature
    </mj-text>
    
    <mj-text>
      Your signature has been recorded successfully. The service provider will review and sign the contract shortly.
    </mj-text>
    """

    cta_url = contract_pdf_url if contract_pdf_url else None
    cta_label = "View Signed Contract" if contract_pdf_url else None

    return get_base_template(
        title="Thank You for Signing!",
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
    """Contract fully executed notification MJML template"""

    total_section = ""
    if total_value:
        total_section = f"<br/>Total: ${total_value:,.2f}"

    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      {business_name} has reviewed and signed your service agreement.
    </mj-text>
    
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Perfect! <strong>{business_name}</strong> has reviewed and signed your service agreement{f' for {property_address}' if property_address else ''}.
    </mj-text>
    
    <mj-text>
      Contract ID: {contract_id}<br/>
      Service Type: {service_type}{total_section}
    </mj-text>
    
    <mj-text>
      ✨ Your signed contract PDF is attached. Your schedule has been confirmed!
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px">
      Questions? Reply here{f' or call {business_phone}' if business_phone else ''}.
    </mj-text>
    
    <mj-text padding="20px 0 0 0">
      Clean regards,<br/><strong>{business_name} Team</strong>
    </mj-text>
    """

    return get_base_template(
        title="Contract Fully Signed!",
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
    """Quote submission confirmation MJML template"""
    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      Thank you for your interest in {business_name}'s services!
    </mj-text>
    
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Thank you for submitting your quote request! We've received your approval and {business_name} will review it shortly.
    </mj-text>
    
    <mj-text align="center" font-size="32px" font-weight="bold" color="{THEME['text_primary']}" padding="20px 0">
      ${quote_amount:,.2f}
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}">
      This is an automated estimate. Final pricing will be confirmed by {business_name}.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="25px 0 0 0">
      <strong>Expected response time:</strong> Within 24-48 hours
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
    """Quote review notification for provider MJML template"""
    review_link = f"https://cleanenroll.com/dashboard/quote-requests/{client_public_id}"

    content = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      <strong>{client_name}</strong> has approved an automated quote and is waiting for your review.
    </mj-text>
    
    <mj-text>
      Name: {client_name}<br/>
      Email: {client_email}<br/>
      Automated Quote: ${quote_amount:,.2f}
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="25px 0 0 0">
      <strong>Recommended response time:</strong> Within 24-48 hours
    </mj-text>
    """

    return get_base_template(
        title="New Quote Approval Request",
        preview_text=f"New Quote Approval Request from {client_name}",
        content_sections=content,
        cta_url=review_link,
        cta_label="Review & Approve Quote",
    )


def quote_approved_template(
    client_name: str,
    business_name: str,
    final_quote_amount: float,
    was_adjusted: bool,
    adjustment_notes: str = None,
    client_public_id: str = None,
) -> str:
    """Quote approved notification MJML template"""
    schedule_link = f"https://cleanenroll.com/client-schedule/{client_public_id}"

    adjustment_section = ""
    if was_adjusted and adjustment_notes:
        adjustment_section = f"""
        <mj-text color="#92400e" font-weight="600" font-size="14px" padding="16px 0 8px 0">
          Quote Adjusted
        </mj-text>
        <mj-text color="#92400e" font-size="14px" padding="0">
          {adjustment_notes}
        </mj-text>
        """

    subject = "Your Quote Has Been Updated" if was_adjusted else "Your Quote Has Been Approved"

    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Great news! {business_name} has reviewed and approved your quote. You're ready to schedule your first cleaning.
    </mj-text>
    
    <mj-text align="center" font-size="36px" font-weight="700" color="{THEME['text_primary']}" padding="20px 0">
      ${final_quote_amount:,.2f}
    </mj-text>
    
    {adjustment_section}
    
    <mj-text padding="24px 0 0 0">
      Click the button below to choose your preferred date and time, review the service agreement, and complete your booking.
    </mj-text>
    """

    return get_base_template(
        title=subject,
        preview_text=f"{subject} - {business_name}",
        content_sections=content,
        cta_url=schedule_link,
        cta_label="Schedule Your First Cleaning",
    )


def payment_received_notification_template(
    provider_name: str,
    client_name: str,
    invoice_number: str,
    amount: float,
    currency: str = "USD",
    payment_date: Optional[str] = None,
) -> str:
    """Payment received notification MJML template"""

    payment_date_section = ""
    if payment_date:
        payment_date_section = f"<br/>Payment Date: {payment_date}"

    content = f"""
    <mj-text color="{THEME['text_muted']}" padding="0 0 24px 0">
      Great news! {client_name} has paid invoice {invoice_number}.
    </mj-text>
    
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      ✨ <strong>Excellent news!</strong> <strong>{client_name}</strong> has just paid their invoice.
    </mj-text>
    
    <mj-text align="center" font-size="32px" color="{THEME['primary']}" font-weight="800" padding="20px 0">
      ${amount:,.2f} {currency}
    </mj-text>
    
    <mj-text align="center" color="{THEME['primary_dark']}" font-size="16px" font-weight="600">
      Payment Received!
    </mj-text>
    
    <mj-text>
      Invoice: {invoice_number}<br/>
      Client: {client_name}{payment_date_section}
    </mj-text>
    
    <mj-text color="#92400e" font-size="14px" font-weight="700" padding="20px 0 0 0">
      💵 Ready for Payout
    </mj-text>
    <mj-text color="#92400e" font-size="13px" padding="0">
      This payment has been added to your available balance and is ready for withdrawal.
    </mj-text>
    """

    return get_base_template(
        title="Payment Received",
        preview_text=f"Payment Received: ${amount:,.2f} from {client_name}",
        content_sections=content,
        cta_url="https://cleanenroll.com/dashboard/payouts",
        cta_label="View Payouts Dashboard",
        is_user_email=True,
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
    "quote_submitted_confirmation_template",
    "quote_review_notification_template",
    "quote_approved_template",
    "payment_received_notification_template",
    "THEME",
    "LOGO_URL",
]


def schedule_confirmed_client_template(
    client_name: str,
    business_name: str,
    scheduled_date: str,
    scheduled_time: str,
) -> str:
    """Schedule confirmed notification for client"""
    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Great news! <strong>{business_name}</strong> has confirmed your preferred cleaning schedule.
    </mj-text>
    
    <mj-text align="center" font-size="18px" font-weight="600" color="{THEME['success']}" padding="20px 0">
      ✓ Confirmed Cleaning Date & Time
    </mj-text>
    
    <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0">
      📅 {scheduled_date}
    </mj-text>
    
    <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0 0 20px 0">
      ⏰ {scheduled_time}
    </mj-text>
    
    <mj-text>
      Your first cleaning is all set! We look forward to serving you.
    </mj-text>
    """

    return get_base_template(
        title="Your Cleaning is Scheduled! 🎉",
        preview_text=f"Cleaning Schedule Confirmed - {business_name}",
        content_sections=content,
    )


def schedule_confirmed_provider_template(
    provider_name: str,
    client_name: str,
    scheduled_date: str,
    scheduled_time: str,
) -> str:
    """Schedule confirmed notification for provider"""
    content = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      You confirmed a cleaning schedule for <strong>{client_name}</strong>.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0">
      📅 {scheduled_date} {scheduled_time}
    </mj-text>
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
    """Alternative time proposed notification for client"""
    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      <strong>{business_name}</strong> has proposed an alternative cleaning time for your convenience.
    </mj-text>
    
    <mj-text align="center" font-size="16px" color="{THEME['primary']}" font-weight="600" padding="20px 0">
      Proposed Alternative Time
    </mj-text>
    
    <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0">
      📅 {proposed_date}
    </mj-text>
    
    <mj-text align="center" font-size="16px" color="{THEME['text_primary']}" padding="0 0 20px 0">
      ⏰ {proposed_time}
    </mj-text>
    
    <mj-text>
      The service provider will reach out to you shortly to confirm this new time or discuss other options that work for both of you.
    </mj-text>
    
    <mj-text color="{THEME['text_muted']}" font-size="14px" padding="20px 0 0 0">
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
    """Alternative time proposed confirmation for provider"""
    content = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      You proposed an alternative time for <strong>{client_name}</strong>.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0">
      Proposed: {proposed_date} {proposed_time}
    </mj-text>
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
    """New schedule request notification for provider"""
    contact_info = ""
    if client_email or client_phone:
        contact_info = f"""
        <mj-text color="{THEME['text_muted']}" font-size="13px" padding="20px 0 0 0">
          Client: {client_name}<br/>
          {f"Email: {client_email}<br/>" if client_email else ""}
          {f"Phone: {client_phone}" if client_phone else ""}
        </mj-text>
        """

    content = f"""
    <mj-text>
      Hi {provider_name},
    </mj-text>
    
    <mj-text>
      <strong>{client_name}</strong> has selected their preferred cleaning time!
    </mj-text>
    
    <mj-text font-size="16px" font-weight="600" color="{THEME['primary']}" padding="20px 0 12px 0">
      📅 Requested Cleaning Schedule
    </mj-text>
    
    <mj-text font-size="15px" color="{THEME['text_primary']}" padding="0">
      <strong>Date:</strong> {scheduled_date}
    </mj-text>
    
    <mj-text font-size="15px" color="{THEME['text_primary']}" padding="0">
      <strong>Time:</strong> {scheduled_time}
    </mj-text>
    
    <mj-text font-size="13px" color="{THEME['text_muted']}" padding="0 0 20px 0">
      Duration: {duration_minutes} minutes
    </mj-text>
    
    <mj-text color="#92400e" font-size="14px" padding="20px 0">
      ⏰ <strong>Action Required:</strong> Please review and confirm this schedule in your dashboard, or propose an alternative time if needed.
    </mj-text>
    
    {contact_info}
    """

    return get_base_template(
        title="Client Selected Cleaning Time! 📅",
        preview_text=f"New Schedule Request from {client_name}",
        content_sections=content,
        cta_url=dashboard_url,
        cta_label="Review Schedule",
        is_user_email=True,
    )


# Update exports
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
    "quote_submitted_confirmation_template",
    "quote_review_notification_template",
    "quote_approved_template",
    "payment_received_notification_template",
    "schedule_confirmed_client_template",
    "schedule_confirmed_provider_template",
    "alternative_time_proposed_client_template",
    "alternative_time_proposed_provider_template",
    "new_schedule_request_template",
    "THEME",
    "LOGO_URL",
]


def payment_confirmation_client_template(
    client_name: str,
    business_name: str,
    amount: float,
    contract_title: str,
    payment_date: str,
) -> str:
    """Payment confirmation for client"""
    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Thank you! Your payment for <strong>{contract_title}</strong> has been successfully processed.
    </mj-text>
    
    <mj-text align="center" font-size="36px" font-weight="700" color="{THEME['success']}" padding="20px 0">
      ${amount:,.2f}
    </mj-text>
    
    <mj-text align="center" color="{THEME['success_light']}" font-size="16px" font-weight="600">
      Payment Received
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0">
      Payment Date: {payment_date}<br/>
      Service: {contract_title}<br/>
      Provider: {business_name}
    </mj-text>
    
    <mj-text font-size="13px" color="{THEME['text_muted']}">
      This is an automated confirmation email. Please do not reply to this message.
    </mj-text>
    """

    return get_base_template(
        title="Payment Received",
        preview_text=f"✅ Payment Received - {contract_title}",
        content_sections=content,
    )


def subscription_activated_template(
    client_name: str,
    business_name: str,
    frequency: str,
    contract_title: str,
    amount: float,
) -> str:
    """Subscription activated notification for client"""
    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Great news! Your <strong>{frequency}</strong> subscription for <strong>{contract_title}</strong> is now active.
    </mj-text>
    
    <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['success']}" padding="20px 0">
      ${amount:,.2f} / {frequency}
    </mj-text>
    
    <mj-text>
      Your card will be automatically charged on the scheduled date. You'll receive a confirmation email after each payment.
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0 0 0">
      Service Provider: {business_name}
    </mj-text>
    """

    return get_base_template(
        title="Subscription Activated! 🎉",
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
    Invoice ready notification for client

    Args:
        is_deposit: If True, shows deposit information
        deposit_percentage: Percentage of deposit
        remaining_balance: Remaining balance after deposit
    """
    due_date_section = ""
    if due_date:
        due_date_section = f"<br/>Due Date: {due_date}"

    # Deposit-specific messaging
    deposit_info = ""
    if is_deposit and remaining_balance:
        total_job_amount = amount + remaining_balance
        deposit_info = f"""
    <mj-text font-size="14px" color="{THEME['text_muted']}" padding="10px 0">
      <strong>Payment Structure:</strong><br/>
      • Total Job Amount: ${total_job_amount:,.2f}<br/>
      • Deposit ({deposit_percentage}%): ${amount:,.2f}<br/>
      • Balance Due After Completion: ${remaining_balance:,.2f}
    </mj-text>
    
    <mj-text>
      This {deposit_percentage}% deposit secures your service appointment. The remaining balance of ${remaining_balance:,.2f} will be invoiced after your service is completed.
    </mj-text>
        """
    elif is_deposit:
        deposit_info = f"""
    <mj-text>
      This is a {deposit_percentage}% deposit to secure your service appointment. The remaining balance will be invoiced after your service is completed.
    </mj-text>
        """

    content = f"""
    <mj-text>
      Hi {client_name},
    </mj-text>
    
    <mj-text>
      Your {'deposit ' if is_deposit else ''}invoice from <strong>{business_name}</strong> is ready for payment.
    </mj-text>
    
    <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['text_primary']}" padding="20px 0">
      ${amount:,.2f}
    </mj-text>
    
    <mj-text font-size="14px" color="{THEME['text_muted']}">
      Invoice: {invoice_number}{due_date_section}
    </mj-text>
    
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


# Update exports
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
