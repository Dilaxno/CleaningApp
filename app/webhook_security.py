"""
Webhook Security Module

Provides centralized, robust signature verification for all webhook endpoints.
Implements best practices:
- Constant-time signature comparison (prevents timing attacks)
- Timestamp validation (prevents replay attacks)
- Request body caching for signature verification
- Detailed logging for security auditing
"""
import hmac
import hashlib
import time
import logging
from typing import Optional, Tuple
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

# Maximum age of webhook in seconds (5 minutes)
MAX_WEBHOOK_AGE_SECONDS = 300


class WebhookSignatureError(Exception):
    """Raised when webhook signature verification fails"""
    pass


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.
    Uses hmac.compare_digest which is designed for this purpose.
    """
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def compute_hmac_sha256(secret: str, payload: bytes) -> str:
    """Compute HMAC-SHA256 signature of payload"""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()


def verify_timestamp(timestamp: Optional[str], max_age: int = MAX_WEBHOOK_AGE_SECONDS) -> bool:
    """
    Verify webhook timestamp is within acceptable range.
    Prevents replay attacks by rejecting old webhooks.
    
    Args:
        timestamp: Unix timestamp as string
        max_age: Maximum age in seconds
    
    Returns:
        True if timestamp is valid, False otherwise
    """
    if not timestamp:
        return True  # Timestamp is optional for some providers
    
    try:
        webhook_time = int(timestamp)
        current_time = int(time.time())
        age = abs(current_time - webhook_time)
        
        if age > max_age:
            logger.warning(f"🚫 Webhook timestamp too old: {age}s (max: {max_age}s)")
            return False
        
        return True
    except (ValueError, TypeError):
        logger.warning(f"🚫 Invalid webhook timestamp format: {timestamp}")
        return False


async def verify_dodo_webhook(
    request: Request,
    secret: str,
    raise_on_failure: bool = True
) -> Tuple[bool, bytes]:
    """
    Verify Dodo Payments webhook signature.
    
    Dodo uses:
    - Header: 'webhook-signature' (HMAC-SHA256 hex digest)
    - Optional: 'webhook-timestamp' for replay protection
    - Optional: 'webhook-id' for idempotency
    
    Args:
        request: FastAPI request object
        secret: Webhook secret from Dodo dashboard
        raise_on_failure: If True, raises HTTPException on failure
    
    Returns:
        Tuple of (is_valid, raw_body)
    """
    raw_body = await request.body()
    signature = request.headers.get("webhook-signature", "")
    timestamp = request.headers.get("webhook-timestamp")
    webhook_id = request.headers.get("webhook-id", "unknown")
    
    # Log webhook receipt (without sensitive data)
    logger.info(f"📥 Dodo webhook received: id={webhook_id}")
    
    # Verify timestamp if provided
    if timestamp and not verify_timestamp(timestamp):
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
        return False, raw_body
    
    # Compute expected signature
    expected_signature = compute_hmac_sha256(secret, raw_body)
    
    # Compare signatures
    if not constant_time_compare(expected_signature, signature):
        logger.warning(f"🚫 Dodo webhook signature mismatch for id={webhook_id}")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        return False, raw_body
    
    logger.info(f"✅ Dodo webhook signature verified: id={webhook_id}")
    return True, raw_body


async def verify_calendly_webhook(
    request: Request,
    secret: str,
    raise_on_failure: bool = True
) -> Tuple[bool, bytes]:
    """
    Verify Calendly webhook signature.
    
    Calendly uses:
    - Header: 'Calendly-Webhook-Signature' (format: "sha256=<hex_digest>")
    
    Args:
        request: FastAPI request object
        secret: Webhook signing key from Calendly
        raise_on_failure: If True, raises HTTPException on failure
    
    Returns:
        Tuple of (is_valid, raw_body)
    """
    raw_body = await request.body()
    signature_header = request.headers.get("Calendly-Webhook-Signature", "")
    
    logger.info("📥 Calendly webhook received")
    
    if not signature_header:
        logger.warning("🚫 Calendly webhook missing signature header")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        return False, raw_body
    
    # Calendly signature format: "sha256=<hex_digest>"
    expected_signature = compute_hmac_sha256(secret, raw_body)
    expected_header = f"sha256={expected_signature}"
    
    if not constant_time_compare(expected_header, signature_header):
        logger.warning("🚫 Calendly webhook signature mismatch")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        return False, raw_body
    
    logger.info("✅ Calendly webhook signature verified")
    return True, raw_body


async def verify_stripe_webhook(
    request: Request,
    secret: str,
    raise_on_failure: bool = True
) -> Tuple[bool, bytes]:
    """
    Verify Stripe webhook signature (if you add Stripe in the future).
    
    Stripe uses:
    - Header: 'Stripe-Signature' (format: "t=<timestamp>,v1=<signature>")
    
    Args:
        request: FastAPI request object
        secret: Webhook endpoint secret from Stripe
        raise_on_failure: If True, raises HTTPException on failure
    
    Returns:
        Tuple of (is_valid, raw_body)
    """
    raw_body = await request.body()
    signature_header = request.headers.get("Stripe-Signature", "")
    
    logger.info("📥 Stripe webhook received")
    
    if not signature_header:
        logger.warning("🚫 Stripe webhook missing signature header")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        return False, raw_body
    
    # Parse Stripe signature header
    elements = dict(item.split("=", 1) for item in signature_header.split(","))
    timestamp = elements.get("t")
    signature = elements.get("v1")
    
    if not timestamp or not signature:
        logger.warning("🚫 Stripe webhook invalid signature format")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Invalid signature format")
        return False, raw_body
    
    # Verify timestamp
    if not verify_timestamp(timestamp):
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
        return False, raw_body
    
    # Compute expected signature (Stripe uses timestamp.payload format)
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected_signature = compute_hmac_sha256(secret, signed_payload.encode())
    
    if not constant_time_compare(expected_signature, signature):
        logger.warning("🚫 Stripe webhook signature mismatch")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        return False, raw_body
    
    logger.info("✅ Stripe webhook signature verified")
    return True, raw_body


def create_webhook_signature(secret: str, payload: bytes, provider: str = "generic") -> str:
    """
    Create a webhook signature for testing or outgoing webhooks.
    
    Args:
        secret: Signing secret
        payload: Request body bytes
        provider: Provider format ('generic', 'calendly', 'stripe')
    
    Returns:
        Signature string in provider's format
    """
    signature = compute_hmac_sha256(secret, payload)
    
    if provider == "calendly":
        return f"sha256={signature}"
    elif provider == "stripe":
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        sig = compute_hmac_sha256(secret, signed_payload.encode())
        return f"t={timestamp},v1={sig}"
    else:
        return signature
