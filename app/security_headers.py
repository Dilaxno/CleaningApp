"""
Security Headers Middleware for FastAPI

Adds security headers to all responses to protect against common web vulnerabilities:
- X-Frame-Options: Prevents clickjacking attacks
- X-Content-Type-Options: Prevents MIME type sniffing
- X-XSS-Protection: Legacy XSS protection (for older browsers)
- Referrer-Policy: Controls referrer information leakage
- Content-Security-Policy: Restricts resource loading
- Strict-Transport-Security: Enforces HTTPS
- Permissions-Policy: Controls browser features
- Cache-Control: Prevents caching of sensitive data
"""

import logging
import os
from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Environment-based configuration
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS", f"{FRONTEND_URL},https://cleanenroll.com,https://www.cleanenroll.com"
)


def get_csp_policy() -> str:
    """
    Generate Content-Security-Policy header value.

    This is configured for an API that serves JSON responses.
    Adjusted to allow framing from frontend domains and Firebase authentication.
    """
    # Get frontend origins for frame-ancestors
    # Allow framing from configured frontend origins plus any custom domains
    frontend_origins = FRONTEND_ORIGINS.split(",")
    # Add wildcard support for custom subdomains (e.g., *.cleanenroll.com)
    frame_ancestors_list = frontend_origins + ["https://*.cleanenroll.com"]
    frame_ancestors = " ".join(frame_ancestors_list)

    # For API backends, we use a restrictive CSP but allow necessary functionality
    directives = [
        "default-src 'self'",  # Allow same-origin by default for API functionality
        f"frame-ancestors {frame_ancestors}",  # Allow embedding from frontend domains and subdomains
        "script-src 'self' https://apis.google.com https://accounts.google.com https://www.gstatic.com https://*.googleapis.com https://static.cloudflareinsights.com https://challenges.cloudflare.com https://player.vimeo.com https://assets.calendly.com https://widget.intercom.io https://js.intercomcdn.com data:",  # Allow Intercom scripts
        "style-src 'self' https://accounts.google.com https://fonts.googleapis.com",  # Removed unsafe-inline
        "font-src 'self' data: https://fonts.gstatic.com https://r2cdn.perplexity.ai https://js.intercomcdn.com",  # Allow Intercom fonts and data URIs
        "img-src 'self' data: blob: https: https://www.google.com https://accounts.google.com https://static.intercomassets.com https://js.intercomcdn.com",  # Allow Intercom images
        "frame-src 'self' https://accounts.google.com https://*.firebaseapp.com https://calendly.com https://*.calendly.com https://intercom-sheets.com https://*.intercom.io",  # Allow Intercom frames
        "connect-src 'self' https://accounts.google.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://*.googleapis.com https://*.firebaseapp.com https://calendly.com https://*.calendly.com https://assets.calendly.com https://api-iam.intercom.io https://api-ping.intercom.io https://nexus-websocket-a.intercom.io wss://nexus-websocket-a.intercom.io https://*.intercom.io",  # Allow Intercom connections
        "media-src 'self' blob: https: https://js.intercomcdn.com",  # Allow Intercom media and blob URLs for video preview
        "base-uri 'none'",  # Prevent base tag injection
        "form-action 'self'",  # Allow form submissions to same origin
    ]

    policy = "; ".join(directives)
    logger.debug(f"🔒 Generated CSP policy: {policy}")
    return policy


def get_permissions_policy() -> str:
    """
    Generate Permissions-Policy header value.

    Disables browser features that aren't needed for an API.
    """
    # Disable all sensitive browser features for API responses
    features = [
        "accelerometer=()",
        "camera=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "payment=()",
        "usb=()",
        "interest-cohort=()",  # Disable FLoC tracking
    ]

    return ", ".join(features)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.

    Headers added:
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: (restrictive policy)
    - Strict-Transport-Security: max-age=31536000; includeSubDomains (production only)
    - Permissions-Policy: (disable unnecessary features)
    - Cache-Control: no-store (for API responses)
    """

    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Skip security headers for excluded paths (e.g., health checks)
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return response

        # X-Frame-Options: Allow framing from same origin
        # SAMEORIGIN allows framing from the same origin (frontend can embed API responses)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # X-Content-Type-Options: Prevent MIME type sniffing
        # Browsers should trust the Content-Type header
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Legacy XSS filter for older browsers
        # Modern browsers use CSP instead, but this helps older ones
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy: Control referrer information
        # strict-origin-when-cross-origin = send full URL for same-origin,
        # only origin for cross-origin, nothing for downgrade
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content-Security-Policy: Restrict resource loading
        response.headers["Content-Security-Policy"] = get_csp_policy()

        # Strict-Transport-Security: Enforce HTTPS (production only)
        # max-age=31536000 = 1 year
        # includeSubDomains = apply to all subdomains
        # preload = allow inclusion in browser preload lists
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Permissions-Policy: Disable unnecessary browser features
        response.headers["Permissions-Policy"] = get_permissions_policy()

        # Cache-Control: Prevent caching of API responses
        # This is important for authenticated endpoints
        # Adjust for specific endpoints that can be cached
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        # X-Permitted-Cross-Domain-Policies: Restrict Adobe cross-domain policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Cross-Origin-Opener-Policy: Isolate browsing context
        # Using same-origin-allow-popups to allow OAuth flows
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"

        # X-DNS-Prefetch-Control: Disable DNS prefetching
        response.headers["X-DNS-Prefetch-Control"] = "off"

        # Note: Cross-Origin-Resource-Policy is NOT set here to allow CORS to work properly
        # The CORS middleware handles cross-origin access control

        return response


def get_security_headers_dict() -> dict:
    """
    Get security headers as a dictionary.
    Useful for adding headers to specific responses.
    """
    headers = {
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": get_csp_policy(),
        "Permissions-Policy": get_permissions_policy(),
        "X-Permitted-Cross-Domain-Policies": "none",
        "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
        "Cache-Control": "no-store, no-cache, must-revalidate",
    }

    if IS_PRODUCTION:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return headers
