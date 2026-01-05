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
 
# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

# Frontend base URL for redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Resend Email Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "CleanEnroll <noreply@cleanenroll.com>")
