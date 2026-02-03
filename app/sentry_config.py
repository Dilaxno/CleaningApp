"""
Sentry configuration for backend error monitoring.
"""

import os
import logging
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize Sentry for error monitoring."""
    
    dsn = os.getenv("SENTRY_DSN")
    environment = os.getenv("SENTRY_ENVIRONMENT", "development")
    
    if not dsn:
        logger.warning("Sentry DSN not provided. Error monitoring disabled.")
        return
    
    # Configure logging integration
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )
    
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
            HttpxIntegration(),
            sentry_logging,
        ],
        
        # Performance monitoring
        traces_sample_rate=0.1 if environment == "production" else 1.0,
        
        # Release tracking
        release=f"cleanenroll-backend@{os.getenv('APP_VERSION', 'unknown')}",
        
        # Filter out noise
        before_send=filter_events,
    )
    
    # Set global tags
    sentry_sdk.set_tag("component", "backend")
    sentry_sdk.set_tag("service", "api")
    
    logger.info(f"Sentry initialized for environment: {environment}")


def filter_events(event, hint):
    """Filter out events that are not useful for monitoring."""
    
    # Filter out common client errors that aren't actionable
    if event.get("level") == "error":
        # Get the exception info
        exc_info = hint.get("exc_info")
        if exc_info:
            exc_type, exc_value, exc_traceback = exc_info
            exc_message = str(exc_value) if exc_value else ""
            
            # Filter out common client-side errors
            noise_patterns = [
                "Connection pool is full",
                "Client disconnected",
                "Broken pipe",
                "Connection reset by peer",
                "SSL: CERTIFICATE_VERIFY_FAILED",
                "timeout",
                "Network is unreachable",
            ]
            
            for pattern in noise_patterns:
                if pattern.lower() in exc_message.lower():
                    return None
    
    # Filter out health check requests
    if event.get("request", {}).get("url", "").endswith("/health"):
        return None
    
    return event


def capture_user_context(user_id: str, email: Optional[str] = None) -> None:
    """Set user context for Sentry."""
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
    })


def capture_business_context(business_id: str, business_name: Optional[str] = None) -> None:
    """Set business context for Sentry."""
    sentry_sdk.set_context("business", {
        "id": business_id,
        "name": business_name,
    })


def add_breadcrumb(message: str, category: str, data: Optional[dict] = None) -> None:
    """Add a breadcrumb for debugging."""
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        data=data or {},
        level="info",
    )


def capture_api_error(error: Exception, endpoint: str, method: str, user_id: Optional[str] = None) -> None:
    """Capture API errors with context."""
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("api_endpoint", endpoint)
        scope.set_tag("http_method", method)
        
        if user_id:
            scope.set_user({"id": user_id})
        
        scope.set_context("api", {
            "endpoint": endpoint,
            "method": method,
        })
        
        sentry_sdk.capture_exception(error)