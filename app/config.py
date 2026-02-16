import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

# Firebase Configuration
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# Cloudflare R2 Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "cleaningapp")

# Dodo Payments Configuration
DODO_PAYMENTS_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY")
DODO_PAYMENTS_WEBHOOK_SECRET = os.getenv("DODO_PAYMENTS_WEBHOOK_SECRET")
# "test_mode" or "live_mode" - default to test for safety
DODO_PAYMENTS_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
# Default tax category used when creating products with the API (configure per business)
DODO_DEFAULT_TAX_CATEGORY = os.getenv("DODO_DEFAULT_TAX_CATEGORY", "digital_products")
# Adhoc product ID for "pay what you want" client payments - prevents creating millions of products
DODO_ADHOC_PRODUCT_ID = os.getenv("DODO_ADHOC_PRODUCT_ID", "pdt_0NWQgv8RX3EG0c34ObKdo")

# Security - CRITICAL: No default secret key in production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    import warnings

    warnings.warn(
        "SECRET_KEY not set! Using insecure default - DO NOT USE IN PRODUCTION", RuntimeWarning, stacklevel=2
    )
    SECRET_KEY = "INSECURE-DEV-KEY-CHANGE-IN-PRODUCTION"  # noqa: S105 - Dev fallback only

# Frontend base URL for redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Resend Email Configuration (fallback)
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "CleanEnroll <noreply@cleanenroll.com>")

# Custom SMTP Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SMTP_ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY")

# Google Calendar OAuth Configuration
# Note: GOOGLE_REDIRECT_URI should point to FRONTEND (not backend API)
# OAuth flow: Google → Frontend → Frontend sends code to Backend API
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{FRONTEND_URL}/auth/google-calendar")

# Square OAuth Configuration
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")  # sandbox or production
SQUARE_APPLICATION_ID = os.getenv("SQUARE_APPLICATION_ID")
SQUARE_APPLICATION_SECRET = os.getenv("SQUARE_APPLICATION_SECRET")
SQUARE_REDIRECT_URI = os.getenv("SQUARE_REDIRECT_URI", f"{FRONTEND_URL}/auth/square/callback")
SQUARE_ENCRYPTION_KEY = os.getenv(
    "SQUARE_ENCRYPTION_KEY"
)  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SQUARE_WEBHOOK_SIGNATURE_KEY = os.getenv(
    "SQUARE_WEBHOOK_SIGNATURE_KEY"
)  # Webhook signature key from Square Dashboard

# QuickBooks OAuth Configuration
QUICKBOOKS_ENVIRONMENT = os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox")  # sandbox or production
QUICKBOOKS_CLIENT_ID = os.getenv("QUICKBOOKS_CLIENT_ID")
QUICKBOOKS_CLIENT_SECRET = os.getenv("QUICKBOOKS_CLIENT_SECRET")
QUICKBOOKS_REDIRECT_URI = os.getenv(
    "QUICKBOOKS_REDIRECT_URI", f"{FRONTEND_URL}/auth/quickbooks/callback"
)
