"""
Cloudflare Turnstile CAPTCHA verification
"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")


async def verify_turnstile(token: str, ip: Optional[str] = None) -> bool:
    """
    Verify Cloudflare Turnstile token
    
    Args:
        token: Turnstile token from client
        ip: Client IP address (optional)
    
    Returns:
        True if verification successful, False otherwise
    """
    if not TURNSTILE_SECRET_KEY:
        logger.warning("⚠️ TURNSTILE_SECRET_KEY not configured - skipping CAPTCHA verification")
        return True  # Fail open if not configured
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                json={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": ip
                },
                timeout=10.0
            )
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                logger.info(f"✅ Turnstile verification successful for IP: {ip}")
            else:
                error_codes = result.get("error-codes", [])
                logger.warning(f"❌ Turnstile verification failed for IP: {ip} - Errors: {error_codes}")
            
            return success
            
    except Exception as e:
        logger.error(f"❌ Turnstile verification error: {str(e)}")
        # Fail open - allow request if verification service is down
        return True
