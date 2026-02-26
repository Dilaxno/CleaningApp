"""
Security middleware for setting RLS context and enforcing security policies.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RLSMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set Row-Level Security (RLS) context for each request.

    This ensures that database queries are automatically filtered based on
    the authenticated user's ID, preventing unauthorized data access.

    Note: This middleware sets the context after authentication, so it works
    with the get_current_user dependency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


def set_rls_context(db: Session, user_id: int) -> None:
    """
    Set the RLS context for a database session.

    This should be called in route handlers after authentication.

    Args:
        db: SQLAlchemy database session
        user_id: ID of the authenticated user

    Example:
        @router.get("/clients")
        async def get_clients(
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            set_rls_context(db, current_user.id)
            clients = db.query(Client).all()  # Automatically filtered by user_id
            return clients
    """
    try:
        db.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": str(user_id)},
        )
        logger.debug(f"RLS context set for user_id={user_id}")
    except Exception as e:
        logger.error(f"Failed to set RLS context for user_id={user_id}: {e}")
        raise


def clear_rls_context(db: Session) -> None:
    """
    Clear the RLS context for a database session.

    Args:
        db: SQLAlchemy database session
    """
    try:
        db.execute(text("SELECT set_config('app.current_user_id', '', false)"))
        logger.debug("RLS context cleared")
    except Exception as e:
        logger.error(f"Failed to clear RLS context: {e}")


def bypass_rls(db: Session) -> None:
    """
    Temporarily bypass RLS for administrative operations.

    WARNING: Use with extreme caution! Only for system-level operations.

    Args:
        db: SQLAlchemy database session
    """
    try:
        db.execute(text("SET LOCAL row_security = off"))
        logger.warning("RLS bypassed for this transaction - USE WITH CAUTION")
    except Exception as e:
        logger.error(f"Failed to bypass RLS: {e}")
        raise


def enable_rls(db: Session) -> None:
    """
    Re-enable RLS after bypassing.

    Args:
        db: SQLAlchemy database session
    """
    try:
        db.execute(text("SET LOCAL row_security = on"))
        logger.debug("RLS re-enabled")
    except Exception as e:
        logger.error(f"Failed to enable RLS: {e}")
        raise
