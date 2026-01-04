import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import auth_router
from .routes.business import router as business_router
from .routes.users import router as users_router
from .routes.clients import router as clients_router
from .routes.upload import router as upload_router
from .routes.contracts import router as contracts_router
from .routes.schedules import router as schedules_router
from .routes.billing import router as billing_router, webhooks_router as dodopayments_webhooks_router
from .routes.contracts_pdf import router as contracts_pdf_router
from .routes.email import router as email_router
from .routes.scheduling import router as scheduling_router
from .routes.calendly import router as calendly_router
from .routes.status_automation import router as status_router
from .routes.trial import router as trial_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    logger.info("🚀 Starting up...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
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


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(business_router)
app.include_router(clients_router)
app.include_router(upload_router)
app.include_router(contracts_router)
app.include_router(contracts_pdf_router)
app.include_router(scheduling_router)
app.include_router(schedules_router)
app.include_router(billing_router)
app.include_router(dodopayments_webhooks_router)
app.include_router(email_router)
app.include_router(calendly_router)
app.include_router(trial_router)


@app.get("/")
def root():
    return {"message": "CleanEnroll API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
