"""
Cloudflare Turnstile CAPTCHA verification
"""

import hashlib
import logging
import os
from typing import Optional

import httpx

from .cache import get_redis_client

logger = logging.getLogger(__name__)

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")


"""
Cloudflare Turnstile CAPTCHA verification
"""
import logging
import os

from .rate_limiter import get_redis_client

logger = logging.getLogger(__name__)

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")


async def verify_turnstile(token: str, ip: Optional[str] = None) -> bool:
    """
    Verify Cloudflare Turnstile token with Redis caching to prevent duplicate verification errors

    Args:
        token: Turnstile token from client
        ip: Client IP address (optional)

    Returns:
        True if verification successful, False otherwise
    """
    if not TURNSTILE_SECRET_KEY:
        logger.warning("⚠️ TURNSTILE_SECRET_KEY not configured - skipping CAPTCHA verification")
        return True  # Fail open if not configured

    # Create a cache key based on token and IP
    cache_key = f"turnstile_verified:{hashlib.sha256(f'{token}:{ip}'.encode()).hexdigest()}"

    try:
        # Check if this token was already verified successfully (using sync Redis)
        try:
            redis_client = get_redis_client()
            if redis_client and redis_client.get(cache_key):
                logger.info(f"✅ Turnstile verification cached for IP: {ip}")
                return True
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis cache check failed: {redis_error}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                json={"secret": TURNSTILE_SECRET_KEY, "response": token, "remoteip": ip},
                timeout=10.0,
            )

            result = response.json()
            success = result.get("success", False)

            if success:
                logger.info(f"✅ Turnstile verification successful for IP: {ip}")
                # Cache successful verification for 5 minutes to allow multiple uses
                try:
                    if redis_client:
                        redis_client.setex(cache_key, 300, "verified")
                except Exception as redis_error:
                    logger.warning(f"⚠️ Redis cache set failed: {redis_error}")
            else:
                error_codes = result.get("error-codes", [])
                logger.warning(
                    f"❌ Turnstile verification failed for IP: {ip} - Errors: {error_codes}"
                )

            return success

    except Exception as e:
        logger.error(f"❌ Turnstile verification error: {str(e)}")
        # Fail open - allow request if verification service is down
        return True
