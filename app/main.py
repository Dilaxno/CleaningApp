import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .csrf import CSRFMiddleware, get_csrf_token_endpoint, CSRF_COOKIE_NAME, generate_csrf_token
from .security_headers import SecurityHeadersMiddleware
from .routes import auth_router
from .routes.business import router as business_router
from .routes.users import router as users_router
from .routes.clients import router as clients_router
from .routes.upload import router as upload_router
from .routes.contracts import router as contracts_router
from .routes.contract_revisions import router as contract_revisions_router
from .routes.schedules import router as schedules_router
from .routes.billing import router as billing_router, webhooks_router as dodopayments_webhooks_router
from .routes.contracts_pdf import router as contracts_pdf_router
from .routes.email import router as email_router
from .routes.scheduling import router as scheduling_router
from .routes.calendly import router as calendly_router
from .routes.calendly_webhooks import router as calendly_webhooks_router
from .routes.scheduling_calendly import router as scheduling_calendly_router
from .routes.google_calendar import router as google_calendar_router
from .routes.scheduling_google_calendar import router as scheduling_google_calendar_router
from .routes.status_automation import router as status_router
from .routes.trial import router as trial_router
from .routes.verification import router as verification_router
from .routes.security import router as security_router
from .routes.notifications import router as notifications_router
from .routes.jobs import router as jobs_router
from .routes.waitlist import router as waitlist_router
from .routes.invoices import router as invoices_router
from .routes.payouts import router as payouts_router
from .routes.smtp import router as smtp_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Security settings from environment
# CSRF is DISABLED by default until frontend integration is complete
# Set CSRF_ENABLED=true to enable once frontend sends X-CSRF-Token headers
CSRF_ENABLED = os.getenv("CSRF_ENABLED", "false").lower() == "true"
SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    logger.info("🚀 Starting up...")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
    
    # Test Redis connection for rate limiting
    try:
        from .rate_limiter import get_redis_client
        redis_client = get_redis_client()
        logger.info("✅ Redis rate limiting is ready")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed - Rate limiting will operate in fail-open mode: {e}")
    
    yield
    # Shutdown
    logger.info("👋 Shutting down...")


app = FastAPI(title="CleanEnroll API", version="1.0.0", lifespan=lifespan)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"➡️  {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"✅ {request.method} {request.url.path} - {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ {request.method} {request.url.path} - Error: {str(e)}")
        raise


# Security Headers Middleware (adds X-Frame-Options, CSP, etc.)
if SECURITY_HEADERS_ENABLED:
    app.add_middleware(SecurityHeadersMiddleware, exclude_paths=["/health", "/docs", "/openapi.json"])
    logger.info("🔒 Security headers enabled")
else:
    logger.warning("⚠️ Security headers DISABLED - only use in development!")


# CSRF Protection Middleware (disabled by default until frontend integration)
if CSRF_ENABLED:
    app.add_middleware(CSRFMiddleware)
    logger.info("🔒 CSRF protection enabled")
else:
    logger.info("ℹ️ CSRF protection disabled - set CSRF_ENABLED=true to enable")


# CORS - must expose csrf_token cookie and allow X-CSRF-Token header
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://cleanenroll.com",
        "https://www.cleanenroll.com",
        "https://coming-soon.cleanenroll.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token"],
    expose_headers=["X-CSRF-Token"],
)

# Routes
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(verification_router)
app.include_router(security_router)
app.include_router(business_router)
app.include_router(clients_router)
app.include_router(upload_router)
app.include_router(contracts_router)
app.include_router(contract_revisions_router)
app.include_router(contracts_pdf_router)
app.include_router(scheduling_router)
app.include_router(schedules_router)
app.include_router(billing_router)
app.include_router(dodopayments_webhooks_router)
app.include_router(email_router)
app.include_router(calendly_router)
app.include_router(calendly_webhooks_router)
app.include_router(scheduling_calendly_router)
app.include_router(google_calendar_router)
app.include_router(scheduling_google_calendar_router)
app.include_router(status_router)
app.include_router(trial_router)
app.include_router(notifications_router)
app.include_router(jobs_router)
app.include_router(waitlist_router)
app.include_router(invoices_router)
app.include_router(payouts_router)
app.include_router(smtp_router)


@app.get("/")
def root():
    return {"message": "CleanEnroll API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


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
        httponly=False,  # Must be readable by JavaScript
        secure=True,  # Only send over HTTPS (set to False for local dev)
        samesite="strict",
        max_age=86400,  # 24 hours
        path="/",
    )
    return {"csrf_token": new_token}
