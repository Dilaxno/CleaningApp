"""
Comprehensive Security Utilities
Provides additional security functions using industry-standard libraries
"""

import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

# Input sanitization
import bleach
from bleach.css_sanitizer import CSSSanitizer

# Token generation and validation
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jose import JWTError
from jose import jwt as jose_jwt

# Password hashing
from passlib.context import CryptContext

# File validation
try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic not available - file type validation will use extensions only")

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# PASSWORD SECURITY
# ============================================================================


def hash_password_bcrypt(password: str) -> str:
    """Hash password using bcrypt (slower but very secure)"""
    return pwd_context.hash(password)


def verify_password_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def check_password_strength(password: str) -> dict[str, Any]:
    """
    Check password strength and return detailed feedback

    Returns:
        dict with 'score' (0-4), 'strength' (weak/fair/good/strong),
        'feedback' (list of suggestions), and 'is_valid' (bool)
    """
    score = 0
    feedback = []

    # Length check
    if len(password) < 8:
        feedback.append("Password must be at least 8 characters long")
    elif len(password) >= 12:
        score += 2
    else:
        score += 1

    # Character variety checks
    if re.search(r"[a-z]", password):
        score += 1
    else:
        feedback.append("Add lowercase letters")

    if re.search(r"[A-Z]", password):
        score += 1
    else:
        feedback.append("Add uppercase letters")

    if re.search(r"\d", password):
        score += 1
    else:
        feedback.append("Add numbers")

    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        feedback.append("Add special characters")

    # Common password check
    common_passwords = ["password", "123456", "qwerty", "admin", "letmein"]
    if password.lower() in common_passwords:
        score = 0
        feedback.append("This is a commonly used password - choose something unique")

    # Determine strength
    if score <= 1:
        strength = "weak"
    elif score == 2:
        strength = "fair"
    elif score == 3:
        strength = "good"
    else:
        strength = "strong"

    return {
        "score": min(score, 4),
        "strength": strength,
        "feedback": feedback,
        "is_valid": len(password) >= 8 and score >= 3,
    }


# ============================================================================
# TOKEN GENERATION & VALIDATION
# ============================================================================


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def generate_timed_token(
    data: dict[str, Any], expires_delta: timedelta = timedelta(hours=1)
) -> str:
    """
    Generate a time-limited token using itsdangerous
    Useful for email verification, password reset, etc.
    """
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    return serializer.dumps(data, salt="security-token")


def verify_timed_token(token: str, max_age: int = 3600) -> Optional[dict[str, Any]]:
    """
    Verify and decode a timed token

    Args:
        token: The token to verify
        max_age: Maximum age in seconds (default 1 hour)

    Returns:
        Decoded data if valid, None if invalid or expired
    """
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    try:
        data = serializer.loads(token, salt="security-token", max_age=max_age)
        return data
    except SignatureExpired:
        logger.warning("Token expired")
        return None
    except BadSignature:
        logger.warning("Invalid token signature")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def create_jwt_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time (default 15 minutes)
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jose_jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> Optional[dict[str, Any]]:
    """
    Verify and decode a JWT token

    Returns:
        Decoded payload if valid, None if invalid or expired
    """
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


# ============================================================================
# INPUT SANITIZATION
# ============================================================================


def sanitize_html(html_content: str, allowed_tags: Optional[list] = None) -> str:
    """
    Sanitize HTML content to prevent XSS attacks

    Args:
        html_content: Raw HTML content
        allowed_tags: List of allowed HTML tags (default: safe subset)

    Returns:
        Sanitized HTML
    """
    if allowed_tags is None:
        # Safe default tags
        allowed_tags = [
            "p",
            "br",
            "strong",
            "em",
            "u",
            "a",
            "ul",
            "ol",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "blockquote",
            "code",
            "pre",
        ]

    allowed_attributes = {"a": ["href", "title", "target"], "*": ["class"]}

    css_sanitizer = CSSSanitizer(
        allowed_css_properties=["color", "background-color", "font-weight"]
    )

    clean_html = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        css_sanitizer=css_sanitizer,
        strip=True,
    )

    return clean_html


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Remove or replace dangerous characters
    filename = re.sub(r"[^\w\s\-\.]", "", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    # Ensure filename is not empty
    if not filename:
        filename = f"file_{generate_secure_token(8)}"

    return filename


def sanitize_sql_identifier(identifier: str) -> str:
    """
    Sanitize SQL identifier (table/column name) to prevent SQL injection
    Note: This is a backup - always use parameterized queries!

    Args:
        identifier: SQL identifier

    Returns:
        Safe identifier
    """
    # Only allow alphanumeric and underscore
    safe_identifier = re.sub(r"[^\w]", "", identifier)

    # Ensure it doesn't start with a number
    if safe_identifier and safe_identifier[0].isdigit():
        safe_identifier = f"_{safe_identifier}"

    return safe_identifier


# ============================================================================
# FILE VALIDATION
# ============================================================================


def validate_file_type(file_path: str, allowed_types: list) -> bool:
    """
    Validate file type by checking actual content (not just extension)

    Args:
        file_path: Path to the file
        allowed_types: List of allowed MIME types

    Returns:
        True if file type is allowed, False otherwise
    """
    if not MAGIC_AVAILABLE:
        # Fallback to extension check
        ext = os.path.splitext(file_path)[1].lower()
        extension_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime_type = extension_map.get(ext)
        return mime_type in allowed_types if mime_type else False

    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        return file_type in allowed_types
    except Exception as e:
        logger.error(f"File type validation error: {e}")
        return False


def validate_image_file(file_path: str) -> bool:
    """Validate that file is actually an image"""
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    return validate_file_type(file_path, allowed_types)


def validate_pdf_file(file_path: str) -> bool:
    """Validate that file is actually a PDF"""
    return validate_file_type(file_path, ["application/pdf"])


# ============================================================================
# SECURITY HEADERS
# ============================================================================


def get_security_headers() -> dict[str, str]:
    """
    Get recommended security headers for HTTP responses

    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }


# ============================================================================
# RATE LIMITING HELPERS
# ============================================================================


def generate_rate_limit_key(identifier: str, endpoint: str) -> str:
    """
    Generate a consistent rate limit key

    Args:
        identifier: User ID, IP address, or other identifier
        endpoint: API endpoint or action name

    Returns:
        Rate limit key
    """
    # Hash the identifier for privacy
    hashed_id = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"rate_limit:{endpoint}:{hashed_id}"


# ============================================================================
# AUDIT LOGGING
# ============================================================================


def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
):
    """
    Log security-related events for audit trail

    Args:
        event_type: Type of security event (login, logout, failed_auth, etc.)
        user_id: User identifier
        ip_address: Client IP address
        details: Additional event details
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "details": details or {},
    }

    # Log to application logger
    logger.info(f"SECURITY_EVENT: {log_entry}")

    # In production, you might want to send this to a dedicated security log service
    # or store in a separate audit table


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal, False otherwise
    """
    return secrets.compare_digest(a.encode(), b.encode())


def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"sk_{generate_secure_token(32)}"


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging/display

    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string
    """
    if len(data) <= visible_chars:
        return "*" * len(data)

    return "*" * (len(data) - visible_chars) + data[-visible_chars:]
