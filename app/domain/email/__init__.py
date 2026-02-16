"""Email domain - Email sending and template management"""

# Note: Email service is kept in original file for now:
# - backend/app/email_service.py - All email functions and templates
#
# This will be refactored in a future phase due to:
# - Complex HTML template rendering with inline CSS
# - 25+ email sending functions for critical business communications
# - SMTP configuration with password encryption
# - Custom SMTP per business logic
# - SVG icon generation
# - Extensive usage across entire codebase
#
# Refactoring requires:
# - Comprehensive email template testing
# - SMTP configuration validation
# - Cross-codebase import updates
# - Staging environment testing

__all__ = []
