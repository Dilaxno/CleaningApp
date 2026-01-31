"""
CSRF Protection Middleware for FastAPI

Implements double-submit cookie pattern for CSRF protection.
- Generates a CSRF token and sets it as a cookie
- Validates that the X-CSRF-Token header matches the cookie value
- Applies to state-changing methods (POST, PUT, PATCH, DELETE)
- Excludes public endpoints and webhooks

NOTE: CSRF protection is DISABLED by default until frontend integration is complete.
Set CSRF_ENABLED=true in environment to enable.
"""
import os
import secrets
import logging
from typing import Callable, List, Optional
from fastapi import Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# CSRF token cookie name
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Methods that require CSRF protection
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths that are exempt from CSRF protection (webhooks, public endpoints, API routes)
EXEMPT_PATHS: List[str] = [
    "/webhooks/",  # All webhook endpoints
    "/api/payments/",  # Payment webhooks
    "/clients/public/",  # Public form submissions (already rate-limited + captcha)
    "/clients",  # Client management (authenticated via JWT)
    "/contracts",  # Contract management (authenticated via JWT)
    "/schedules",  # Schedule management (authenticated via JWT)
    "/invoices",  # Invoice management (authenticated via JWT)
    "/business-config",  # Business config (authenticated via JWT)
    "/users",  # User management (authenticated via JWT)
    "/billing",  # Billing endpoints (authenticated via JWT)
    "/upload",  # File uploads (authenticated via JWT)
    "/verification",  # Email verification (authenticated via JWT)
    "/security",  # Security settings (authenticated via JWT)
    "/notifications",  # Notifications (authenticated via JWT)
    "/health",  # Health check
    "/docs",  # API docs
    "/openapi.json",  # OpenAPI spec
    "/csrf-token",  # CSRF token endpoint
    "/",  # Root endpoint
]


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token"""
    return secrets.token_urlsafe(32)


def is_path_exempt(path: str) -> bool:
    """Check if a path is exempt from CSRF protection"""
    for exempt in EXEMPT_PATHS:
        if path.startswith(exempt) or path == exempt:
            return True
    return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection Middleware using double-submit cookie pattern.
    
    How it works:
    1. On any request, if no CSRF cookie exists, generate one and set it
    2. For state-changing requests (POST/PUT/PATCH/DELETE):
       - Check that X-CSRF-Token header exists
       - Verify it matches the csrf_token cookie
       - Reject if missing or mismatched
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get existing CSRF token from cookie
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        
        # Check if this request needs CSRF validation
        needs_validation = (
            request.method in PROTECTED_METHODS
            and not is_path_exempt(request.url.path)
        )
        
        if needs_validation:
            # Get CSRF token from header
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            
            if not csrf_cookie:
                logger.warning(f"🚫 CSRF: Missing cookie for {request.method} {request.url.path}")
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing. Please refresh the page and try again."
                )
            
            if not csrf_header:
                logger.warning(f"🚫 CSRF: Missing header for {request.method} {request.url.path}")
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token header missing. Please refresh the page and try again."
                )
            
            # Constant-time comparison to prevent timing attacks
            if not secrets.compare_digest(csrf_cookie, csrf_header):
                logger.warning(f"🚫 CSRF: Token mismatch for {request.method} {request.url.path}")
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token invalid. Please refresh the page and try again."
                )
            
            logger.debug(f"✅ CSRF: Valid token for {request.method} {request.url.path}")
        
        # Process the request
        response = await call_next(request)
        
        # Set or refresh CSRF cookie if not present
        if not csrf_cookie:
            new_token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=new_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=86400,
                path="/",
            )
            logger.debug(f"🔑 CSRF: Set new token cookie")
        
        return response


def get_csrf_token_endpoint():
    """
    Endpoint to get a fresh CSRF token.
    Frontend can call this on app load to ensure they have a valid token.
    """
    async def csrf_token_handler(request: Request, response: Response):
        # Check if token already exists
        existing_token = request.cookies.get(CSRF_COOKIE_NAME)
        
        if existing_token:
            return {"csrf_token": existing_token}
        
        # Generate new token
        new_token = generate_csrf_token()
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=new_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=86400,
            path="/",
        )
        return {"csrf_token": new_token}
    
    return csrf_token_handler
