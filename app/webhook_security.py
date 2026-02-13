"""
Webhook Security Module

Provides centralized, robust signature verification for all webhook endpoints.
Implements best practices:
- Constant-time signature comparison (prevents timing attacks)
- Timestamp validation (prevents replay attacks)
- Request body caching for signature verification
- Detailed logging for security auditing
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import HTTPException, Request

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
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def compute_hmac_sha256_base64(secret: str, payload: bytes) -> str:
    """Compute HMAC-SHA256 signature of payload and return base64 encoded"""
    import base64

    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(signature).decode("utf-8")


def extract_svix_signing_key(secret: str) -> bytes:
    """
    Extract Svix/Standard Webhooks signing key bytes from a Dodo/whsec_ style secret.

    - Incoming secret typically looks like: "whsec_BASE64KEY"
    - The HMAC key must be the BASE64-decoded bytes of the part after "whsec_"
    - If not prefixed, attempt base64 decode; if that fails, fall back to UTF-8 bytes
    """
    try:
        if secret.startswith("whsec_"):
            b64_part = secret[6:]
            return base64.b64decode(b64_part)
        # Try decoding entire secret as base64 if no prefix
        return base64.b64decode(secret)
    except Exception:
        # Fallback to raw utf-8 bytes if not valid base64
        return secret.encode("utf-8")


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
    request: Request, secret: str, raise_on_failure: bool = True
) -> tuple[bool, bytes]:
    """
    Verify Dodo Payments webhook signature using Standard Webhooks specification.

    According to Dodo's documentation, the signed message format is:
    webhook-id.webhook-timestamp.payload (separated by periods)

    Args:
        request: FastAPI request object
        secret: Webhook secret from Dodo dashboard
        raise_on_failure: If True, raises HTTPException on failure

    Returns:
        Tuple of (is_valid, raw_body)
    """
    # Get raw body BEFORE any parsing - this is critical
    raw_body = await request.body()

    # Get required headers
    signature_header = request.headers.get("webhook-signature", "")
    timestamp = request.headers.get("webhook-timestamp", "")
    webhook_id = request.headers.get("webhook-id", "unknown")

    # Log webhook receipt
    logger.info(f"📥 Dodo webhook received: id={webhook_id}")
    logger.info(f"🔍 Headers: signature={signature_header}, timestamp={timestamp}")

    # Validate required headers
    if not signature_header:
        logger.error("❌ Missing webhook-signature header")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        return False, raw_body

    if not timestamp:
        logger.error("❌ Missing webhook-timestamp header")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Missing webhook timestamp")
        return False, raw_body

    # Verify timestamp (prevent replay attacks)
    if not verify_timestamp(timestamp):
        logger.error("❌ Webhook timestamp expired or invalid")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
        return False, raw_body

    # Parse signature header (format: "v1,{signature}")
    if not signature_header.startswith("v1,"):
        logger.error(f"❌ Invalid signature format: {signature_header[:20]}...")
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Invalid signature format")
        return False, raw_body

    received_signature = signature_header[3:]  # Remove "v1," prefix

    # Prepare Svix key bytes and byte-perfect signed message: id.timestamp.payload
    signing_key = extract_svix_signing_key(secret)
    logger.info(f"🔑 Webhook signing key bytes length: {len(signing_key)}")
    signed_message_bytes = b".".join(
        [webhook_id.encode("utf-8"), timestamp.encode("utf-8"), raw_body]
    )

    expected_signature = base64.b64encode(
        hmac.new(signing_key, signed_message_bytes, hashlib.sha256).digest()
    ).decode("utf-8")

    # Log verification details
    logger.info("🔍 Dodo webhook verification details:")
    logger.info(f"🔍 Webhook ID: {webhook_id}")
    logger.info(f"🔍 Timestamp: {timestamp}")
    logger.info(f"🔍 Raw body length: {len(raw_body)} bytes")
    logger.info("🔍 Signed message format: webhook-id.webhook-timestamp.payload")
    logger.info(f"🔍 Signed message length: {len(signed_message_bytes)} bytes")
    logger.info(f"🔍 Expected signature: {expected_signature}")
    logger.info(f"🔍 Received signature: {received_signature}")

    # Verify signature using constant-time comparison
    if constant_time_compare(expected_signature, received_signature):
        logger.info(f"✅ Dodo webhook signature verified successfully: {webhook_id}")
        return True, raw_body

    # Primary signature verification failed, try legacy method as fallback
    logger.warning(
        f"⚠️ Primary Dodo webhook signature verification failed for {webhook_id}, trying legacy method..."
    )

    # Try legacy verification method
    try:
        is_valid_legacy, _ = await verify_dodo_webhook_legacy(
            request, secret, raise_on_failure=False
        )
        if is_valid_legacy:
            logger.info(f"✅ Dodo webhook signature verified using legacy method: {webhook_id}")
            return True, raw_body
    except Exception as e:
        logger.warning(f"⚠️ Legacy verification also failed: {e}")

    # Both methods failed - signature verification failed
    logger.error(f"❌ Dodo webhook signature mismatch for {webhook_id}")
    logger.error("❌ Both primary and legacy verification methods failed")
    logger.info("🔍 Debug info:")
    logger.info(f"🔍 Raw body (first 200 chars): {raw_body[:200]}")
    logger.info(f"🔍 Raw body (last 200 chars): {raw_body[-200:]}")
    logger.info("🔍 Byte-perfect payload construction used")

    if raise_on_failure:
        raise HTTPException(status_code=401, detail="Invalid webhook signature") from e
    return False, raw_body


async def verify_dodo_webhook_legacy(
    request: Request, secret: str, raise_on_failure: bool = True
) -> tuple[bool, bytes]:
    """
    Legacy Dodo Payments webhook signature verification with multiple format attempts.
    This is kept as a fallback in case the main verification fails.
    """
    raw_body = await request.body()
    signature = request.headers.get("webhook-signature", "")
    timestamp = request.headers.get("webhook-timestamp")
    webhook_id = request.headers.get("webhook-id", "unknown")

    # Log all headers for debugging
    logger.info(f"🔍 All webhook headers for {webhook_id}: {dict(request.headers)}")

    # Check for alternative signature headers that Dodo might use
    alt_signatures = {
        "webhook-signature": request.headers.get("webhook-signature", ""),
        "x-webhook-signature": request.headers.get("x-webhook-signature", ""),
        "dodo-signature": request.headers.get("dodo-signature", ""),
        "x-dodo-signature": request.headers.get("x-dodo-signature", ""),
        "signature": request.headers.get("signature", ""),
    }

    logger.info(f"🔍 Signature headers found: {alt_signatures}")

    # Use the first non-empty signature we find
    for header_name, header_value in alt_signatures.items():
        if header_value:
            signature = header_value
            logger.info(f"🔍 Using signature from header: {header_name}")
            break

    # Log webhook receipt (without sensitive data)
    logger.debug(f"📥 Dodo webhook received: id={webhook_id}")

    # Verify timestamp if provided
    if timestamp and not verify_timestamp(timestamp):
        if raise_on_failure:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
        return False, raw_body

    # Process the secret - some providers expect it without the prefix
    secrets_to_try = [secret]
    if secret.startswith("whsec_"):
        secrets_to_try.append(secret[6:])  # Remove "whsec_" prefix

    # Try each secret variant
    for secret_variant in secrets_to_try:
        logger.info(f"🔍 Trying secret variant starting with: {secret_variant[:10]}...")

        # Compute expected signature with different methods and formats
        expected_signature_hex = compute_hmac_sha256(secret_variant, raw_body)
        expected_signature_base64 = compute_hmac_sha256_base64(secret_variant, raw_body)

        # Try timestamp + body (some providers do this)
        expected_with_timestamp_hex = ""
        expected_with_timestamp_base64 = ""
        if timestamp:
            timestamp_payload = f"{timestamp}.{raw_body.decode('utf-8', errors='ignore')}"
            expected_with_timestamp_hex = compute_hmac_sha256(
                secret_variant, timestamp_payload.encode()
            )
            expected_with_timestamp_base64 = compute_hmac_sha256_base64(
                secret_variant, timestamp_payload.encode()
            )

        # Special handling for v1,<signature> format (Stripe-style)
        if signature.startswith("v1,"):
            signature_without_prefix = signature[3:]  # Remove "v1," prefix
            logger.info(
                f"🔍 Detected v1 signature format, signature without prefix: {signature_without_prefix}"
            )

            # For Dodo, try the most common payload constructions
            v1_payloads = [
                ("raw_body", raw_body),
            ]

            if timestamp:
                # Dodo might use timestamp.body format (like Stripe)
                timestamp_dot_body = f"{timestamp}.{raw_body.decode('utf-8', errors='ignore')}"
                v1_payloads.append(("timestamp_dot_body", timestamp_dot_body.encode()))

            for payload_name, payload in v1_payloads:
                expected_v1_base64 = compute_hmac_sha256_base64(secret_variant, payload)

                logger.info(f"🔍 Trying v1 {payload_name} - base64: {expected_v1_base64[:20]}...")

                if constant_time_compare(expected_v1_base64, signature_without_prefix):
                    logger.info(
                        f"✅ v1 signature matched using {payload_name} base64 with secret variant {secret_variant[:10]}..."
                    )
                    return True, raw_body

        # Try different signature formats that Dodo might use
        signature_candidates = [
            ("hex", expected_signature_hex),
            ("base64", expected_signature_base64),
            ("sha256=hex", f"sha256={expected_signature_hex}"),
            ("sha256=base64", f"sha256={expected_signature_base64}"),
        ]

        # Handle Stripe-style v1,<signature> format
        if signature.startswith("v1,"):
            signature_without_prefix = signature[3:]  # Remove "v1," prefix
            signature_candidates.extend(
                [
                    ("v1_hex", expected_signature_hex),
                    ("v1_base64", expected_signature_base64),
                    ("v1_sha256=hex", f"sha256={expected_signature_hex}"),
                    ("v1_sha256=base64", f"sha256={expected_signature_base64}"),
                ]
            )
            # Also try comparing against the signature without prefix
            for method, expected in [
                ("v1_stripped_hex", expected_signature_hex),
                ("v1_stripped_base64", expected_signature_base64),
            ]:
                if constant_time_compare(expected, signature_without_prefix):
                    logger.info(
                        f"✅ Signature matched using {method} with secret variant {secret_variant[:10]}..."
                    )
                    logger.debug(f"✅ Dodo webhook signature verified: id={webhook_id}")
                    return True, raw_body

        if expected_with_timestamp_hex:
            signature_candidates.extend(
                [
                    ("timestamp_body_hex", expected_with_timestamp_hex),
                    ("timestamp_body_base64", expected_with_timestamp_base64),
                    ("sha256_timestamp_body_hex", f"sha256={expected_with_timestamp_hex}"),
                    ("sha256_timestamp_body_base64", f"sha256={expected_with_timestamp_base64}"),
                ]
            )

            # Handle v1 format with timestamp
            if signature.startswith("v1,"):
                signature_without_prefix = signature[3:]
                signature_candidates.extend(
                    [
                        ("v1_timestamp_body_hex", expected_with_timestamp_hex),
                        ("v1_timestamp_body_base64", expected_with_timestamp_base64),
                    ]
                )
                # Try comparing timestamp variants against signature without prefix
                for method, expected in [
                    ("v1_stripped_timestamp_body_hex", expected_with_timestamp_hex),
                    ("v1_stripped_timestamp_body_base64", expected_with_timestamp_base64),
                ]:
                    if constant_time_compare(expected, signature_without_prefix):
                        logger.info(
                            f"✅ Signature matched using {method} with secret variant {secret_variant[:10]}..."
                        )
                        logger.debug(f"✅ Dodo webhook signature verified: id={webhook_id}")
                        return True, raw_body

        # Compare all possible signature formats
        for method, expected in signature_candidates:
            if constant_time_compare(expected, signature):
                logger.info(
                    f"✅ Signature matched using {method} with secret variant {secret_variant[:10]}..."
                )
                logger.debug(f"✅ Dodo webhook signature verified: id={webhook_id}")
                return True, raw_body

    # If we get here, no signature matched
    logger.warning(f"🚫 Dodo webhook signature mismatch for id={webhook_id}")
    logger.info(f"🔍 Signature debug for webhook {webhook_id}:")
    logger.info(f"🔍 Received signature: '{signature}'")
    logger.info(f"🔍 Timestamp: '{timestamp}'")
    logger.info(f"🔍 Raw body length: {len(raw_body)}")
    logger.info(f"🔍 Raw body (first 200 chars): {raw_body[:200]}")

    if raise_on_failure:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return False, raw_body


async def verify_calendly_webhook(
    request: Request, secret: str, raise_on_failure: bool = True
) -> tuple[bool, bytes]:
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

    logger.debug("📥 Calendly webhook received")

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

    logger.debug("✅ Calendly webhook signature verified")
    return True, raw_body


async def verify_stripe_webhook(
    request: Request, secret: str, raise_on_failure: bool = True
) -> tuple[bool, bytes]:
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

    logger.debug("📥 Stripe webhook received")

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

    logger.debug("✅ Stripe webhook signature verified")
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
