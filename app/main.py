import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

# Import all models to ensure they're registered with SQLAlchemy Base
# This is needed for relationships between models in different files
from . import (
    models,  # noqa: F401
    models_google_calendar,  # noqa: F401
    models_invoice,  # noqa: F401
    models_quickbooks,  # noqa: F401
    models_square,  # noqa: F401
    models_twilio,  # noqa: F401
    models_visit,  # noqa: F401
)
from .csrf import CSRF_COOKIE_NAME, CSRFMiddleware, generate_csrf_token
from .database import Base, engine, get_db
from .routes import auth_router

# NEW: Use domain-driven billing router
from .domain.billing import router as billing_router
from .domain.billing import webhooks_router as dodopayments_webhooks_router
from .routes.business import router as business_router
from .routes.clients import router as clients_router
from .routes.contract_revisions import router as contract_revisions_router

# NEW: Use domain-driven contracts router for CRUD operations
from .domain.contracts import router as contracts_router

# Keep original contracts_pdf router for PDF generation (will be integrated later)
from .routes.contracts_pdf import router as contracts_pdf_router
from .routes.email import router as email_router
from .routes.geocoding import router as geocoding_router
from .routes.google_calendar import router as google_calendar_router
from .routes.integration_requests import router as integration_requests_router
from .routes.intercom import router as intercom_router
from .routes.invoices import router as invoices_router
from .routes.jobs import router as jobs_router
from .routes.nominatim_geocoding import router as nominatim_geocoding_router
from .routes.notifications import router as notifications_router
from .routes.payouts import router as payouts_router
from .routes.property_shots import router as property_shots_router
from .routes.quickbooks import router as quickbooks_router
from .routes.schedules import router as schedules_router
from .routes.scheduling import router as scheduling_router
from .routes.security import router as security_router
from .routes.service_areas import router as service_areas_router
from .routes.smarty_geocoding import router as smarty_geocoding_router
from .routes.smtp import router as smtp_router
from .routes.square import router as square_router
from .routes.square_webhooks import router as square_webhooks_router
from .routes.status_automation import router as status_router
from .routes.subdomain import router as subdomain_router
from .routes.template_selection import router as template_selection_router
from .routes.templates import router as templates_router
from .routes.twilio import router as twilio_router
from .routes.upload import router as upload_router
from .routes.users import router as users_router
from .routes.verification import router as verification_router
from .routes.visits import router as visits_router
from .routes.scope_templates import router as scope_templates_router
from .routes.embed import router as embed_router
from .routes.scope_proposals import router as scope_proposals_router
from .security_headers import SecurityHeadersMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Reduce verbosity of third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Security settings from environment
# CSRF is ENABLED by default for security
# Set CSRF_ENABLED=false only for development/testing
CSRF_ENABLED = os.getenv("CSRF_ENABLED", "true").lower() == "true"
SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Database tables created successfully")
    except Exception as e:
        # Ignore "already exists" errors from race conditions between workers
        error_msg = str(e)
        if "already exists" in error_msg or "duplicate key" in error_msg:
            logger.info("Database tables already exist (created by another worker)")
        else:
            logger.error(f"Failed to create database tables: {e}")

    try:
        from .rate_limiter import get_redis_client

        _redis_client = get_redis_client()  # Connection test
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(
            f"Redis connection failed - Rate limiting will operate in fail-open mode: {e}"
        )

    yield
    logger.info("Application shutting down...")


app = FastAPI(title="CleanEnroll API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Convert 422 validation errors from HTTPBearer to 401 authentication errors
    when the issue is with the Authorization header
    """
    # Check if the error is related to Authorization header
    for error in exc.errors():
        if error.get("loc") and "authorization" in str(error.get("loc")).lower():
            logger.warning(
                f"Authentication failed for {request.url.path}: Missing or invalid Authorization header"
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Not authenticated. Please provide a valid Bearer token in the Authorization header."
                },
            )

    # For other validation errors, return 422 as normal
    logger.warning(f"Validation error for {request.url.path}: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.middleware("http")
async def custom_domain_resolver(request: Request, call_next):
    """
    Middleware to resolve custom domains to user IDs for template access.
    This enables secure access to templates via custom domains like forms.cleaningco.com
    """
    host = request.headers.get("host", "").lower()

    # Skip resolution for main domain and localhost
    if (
        host.startswith("localhost")
        or host.startswith("127.0.0.1")
        or host.endswith("cleanenroll.com")
        or host.endswith("api.cleanenroll.com")
    ):
        return await call_next(request)

    # Only resolve for template-related endpoints
    path = request.url.path
    if not (
        path.startswith("/templates/public/")
        or path.startswith("/form/")
        or path.startswith("/embed/")
        or path.startswith("/business/public/")
        or path.startswith("/clients/public/")
    ):
        return await call_next(request)

    try:
        # Look up user by custom domain
        db: Session = next(get_db())
        from .models import BusinessConfig

        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.custom_forms_domain == host).first()
        )

        if business_config and business_config.user:
            # Add resolved user info to request state for use in endpoints
            request.state.custom_domain_user_id = business_config.user.id
            request.state.custom_domain_user_uid = business_config.user.firebase_uid
            request.state.is_custom_domain = True
        else:
            # Custom domain not found - this could be a security issue
            logger.warning(f"Unknown custom domain attempted: {host} for path {path}")
            request.state.is_custom_domain = False

        db.close()
    except Exception as e:
        logger.error(f"Custom domain resolution failed for {host}: {e}")
        request.state.is_custom_domain = False

    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"{request.method} {request.url.path} - Error: {str(e)}")
        raise


if SECURITY_HEADERS_ENABLED:
    app.add_middleware(
        SecurityHeadersMiddleware, exclude_paths=["/health", "/docs", "/openapi.json"]
    )
    logger.info("Security headers enabled")
else:
    logger.warning("Security headers DISABLED - only use in development!")

if CSRF_ENABLED:
    app.add_middleware(CSRFMiddleware)
    logger.info("CSRF protection enabled")
else:
    logger.info("CSRF protection disabled")


# CORS Configuration
# For production with credentials (cookies), we need specific origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://cleanenroll.com,https://www.cleanenroll.com,http://localhost:5173,http://localhost:3000",
).split(",")

# Log CORS configuration for debugging
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Enable credentials for CSRF cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Routes
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(verification_router)
app.include_router(security_router)
app.include_router(business_router, prefix="/business")
app.include_router(clients_router)
app.include_router(upload_router)
app.include_router(property_shots_router)
app.include_router(contracts_router)
app.include_router(contract_revisions_router)
app.include_router(contracts_pdf_router)
app.include_router(scheduling_router)
app.include_router(schedules_router)
app.include_router(billing_router)
app.include_router(dodopayments_webhooks_router)
app.include_router(email_router)
app.include_router(status_router)
app.include_router(notifications_router)
app.include_router(jobs_router)
app.include_router(invoices_router)
app.include_router(payouts_router)
app.include_router(smtp_router)
app.include_router(subdomain_router)
app.include_router(integration_requests_router)
app.include_router(geocoding_router)
app.include_router(smarty_geocoding_router)
app.include_router(nominatim_geocoding_router)
app.include_router(templates_router)
app.include_router(template_selection_router)
app.include_router(service_areas_router)
app.include_router(square_router)
app.include_router(square_webhooks_router)
app.include_router(google_calendar_router)
app.include_router(quickbooks_router)
app.include_router(twilio_router)
app.include_router(intercom_router)
app.include_router(visits_router)
app.include_router(scope_templates_router)
app.include_router(scope_proposals_router)
app.include_router(embed_router)


# Square OAuth callback routes (must match redirect URI exactly)
# Supporting both /auth/square/callback and /square/oauth/callback for flexibility
@app.get("/auth/square/callback")
async def square_oauth_callback_auth(code: str, state: str | None = None):
    """
    Square OAuth callback - redirects to frontend
    This route matches the redirect URI registered in Square Dashboard
    """
    from fastapi.responses import RedirectResponse

    from .config import FRONTEND_URL

    # Redirect to frontend callback handler with the code and state
    frontend_callback = f"{FRONTEND_URL}/auth/square/callback?code={code}&state={state or ''}"
    return RedirectResponse(url=frontend_callback)


@app.get("/square/oauth/callback")
async def square_oauth_callback_legacy(code: str, state: str | None = None):
    """
    Square OAuth callback (legacy path) - redirects to frontend
    This route supports the old redirect URI path
    """
    from fastapi.responses import RedirectResponse

    from .config import FRONTEND_URL

    # Redirect to frontend callback handler with the code and state
    frontend_callback = f"{FRONTEND_URL}/auth/square/callback?code={code}&state={state or ''}"
    return RedirectResponse(url=frontend_callback)


@app.get("/")
def root():
    return {"message": "CleanEnroll API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/debug/cors")
def debug_cors(request: Request):
    """Debug endpoint to check CORS configuration"""
    return {
        "origin": request.headers.get("origin"),
        "host": request.headers.get("host"),
        "user_agent": request.headers.get("user-agent"),
        "allowed_origins": ALLOWED_ORIGINS,
        "timestamp": time.time(),
    }


@app.get("/health/redis")
async def redis_health_check():
    """Check Redis connectivity for monitoring"""
    try:
        from .rate_limiter import get_redis_client

        redis_client = get_redis_client()

        # Test basic connectivity
        start_time = time.time()
        redis_client.ping()
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Get Redis info
        info = redis_client.info()

        return {
            "status": "healthy",
            "redis": {
                "connected": True,
                "response_time_ms": round(response_time, 2),
                "version": info.get("redis_version", "unknown"),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            },
        }
    except Exception as e:
        return {"status": "unhealthy", "redis": {"connected": False, "error": str(e)}}


@app.get("/csrf-token")
async def get_csrf_token(request: Request, response: Response):
    """
    Get a CSRF token for the frontend.
    The token is also set as a cookie.
    Frontend should include this token in X-CSRF-Token header for state-changing requests.
    """
    existing_token = request.cookies.get(CSRF_COOKIE_NAME)

    if existing_token:
        return {"csrf_token": existing_token}

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
