"""Shared validation utilities"""

import re
import uuid
from typing import Optional


def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def validate_us_phone(phone: Optional[str]) -> Optional[str]:
    """
    Validate and normalize US phone number to E.164 format.

    Args:
        phone: Phone number string in various formats

    Returns:
        Normalized phone number in E.164 format (+1XXXXXXXXXX)

    Raises:
        ValueError: If phone number is invalid
    """
    if not phone:
        return phone

    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    # Handle +1 prefix
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]

    # US phone numbers should have 10 digits
    if len(digits) != 10:
        raise ValueError("Phone number must be 10 digits for US numbers")

    # Format as E.164 for storage
    return f"+1{digits}"


def validate_email(email: Optional[str]) -> Optional[str]:
    """
    Validate email format.

    Args:
        email: Email address string

    Returns:
        Lowercase email address

    Raises:
        ValueError: If email format is invalid
    """
    if not email:
        return email

    email = email.strip().lower()

    # Basic email validation pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        raise ValueError("Invalid email format")

    return email


# List of common free email providers
FREE_EMAIL_PROVIDERS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "mail.com",
    "protonmail.com",
    "zoho.com",
    "yandex.com",
    "gmx.com",
    "inbox.com",
    "live.com",
    "msn.com",
    "me.com",
    "mac.com",
    "googlemail.com",
    "yahoo.co.uk",
    "yahoo.co.in",
    "yahoo.fr",
    "yahoo.de",
    "hotmail.co.uk",
    "hotmail.fr",
    "outlook.fr",
    "outlook.de",
}


def validate_corporate_email(email: Optional[str]) -> Optional[str]:
    """
    Validate corporate email format (no free email providers).

    Args:
        email: Email address string

    Returns:
        Lowercase email address

    Raises:
        ValueError: If email format is invalid or is from a free provider
    """
    if not email:
        return email

    # First validate basic email format
    email = validate_email(email)

    # Extract domain
    domain = email.split("@")[1].lower()

    # Check if it's a free email provider
    if domain in FREE_EMAIL_PROVIDERS:
        raise ValueError("Please use your company business email address, not a personal email")

    return email


def validate_subdomain(subdomain: str) -> str:
    """
    Validate subdomain format.

    Args:
        subdomain: Subdomain string (e.g., mail.example.com)

    Returns:
        Lowercase, stripped subdomain

    Raises:
        ValueError: If subdomain format is invalid
    """
    if not subdomain:
        raise ValueError("Subdomain is required")

    # Basic domain validation
    domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
    if not re.match(domain_pattern, subdomain):
        raise ValueError("Invalid subdomain format")

    # Must be a subdomain (contain at least one dot)
    if "." not in subdomain:
        raise ValueError("Must be a subdomain (e.g., mail.yourdomain.com)")

    return subdomain.lower().strip()
