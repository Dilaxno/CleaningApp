#!/usr/bin/env python3
"""
ARQ Worker for background jobs - optimized for contract signing performance.

This worker handles:
- PDF regeneration (5-30 seconds → background)
- Email sending (1-5 seconds → background)  
- File uploads (1-3 seconds → background)
- Client count increments (database writes → background)

Usage:
    python worker.py

Environment Variables:
    REDIS_URL - Redis connection URL for ARQ
    DATABASE_URL - PostgreSQL connection URL
"""

import asyncio
import logging
import os
import sys

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, trying environment variables directly")

from arq import create_pool
from arq.connections import RedisSettings

# Import background job functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.background_jobs import (
    regenerate_contract_pdf_job,
    send_contract_emails_job,
    upload_client_signature_job,
    increment_client_count_job
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis configuration for ARQ
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_settings = RedisSettings.from_dsn(REDIS_URL)

async def startup(ctx):
    """Worker startup - initialize connections"""
    logger.info("🚀 ARQ Worker starting up...")
    logger.info(f"📡 Redis: {REDIS_URL}")
    logger.info("📋 Registered jobs:")
    logger.info("  - regenerate_contract_pdf_job (PDF generation)")
    logger.info("  - send_contract_emails_job (Email notifications)")
    logger.info("  - upload_client_signature_job (File uploads)")
    logger.info("  - increment_client_count_job (Plan limits)")

async def shutdown(ctx):
    """Worker shutdown - cleanup connections"""
    logger.info("🛑 ARQ Worker shutting down...")

# Worker class configuration
class WorkerSettings:
    """ARQ Worker settings optimized for contract signing performance"""
    
    # Redis connection
    redis_settings = redis_settings
    
    # Job functions
    functions = [
        regenerate_contract_pdf_job,
        send_contract_emails_job,
        upload_client_signature_job,
        increment_client_count_job,
    ]
    
    # Worker configuration
    on_startup = startup
    on_shutdown = shutdown
    
    # Performance settings
    max_jobs = 10           # Process up to 10 jobs concurrently
    job_timeout = 300       # 5 minute timeout for jobs
    keep_result = 3600      # Keep job results for 1 hour
    
    # Retry configuration
    max_tries = 3           # Retry failed jobs up to 3 times
    retry_delay = 30        # Wait 30 seconds between retries
    
    # Health check
    health_check_interval = 30  # Check worker health every 30 seconds

if __name__ == "__main__":
    """Run the ARQ worker"""
    from arq import run_worker
    
    logger.info("🔧 Starting ARQ Worker for contract signing optimization...")
    logger.info("💡 This worker handles slow operations in the background:")
    logger.info("   • PDF regeneration: 5-30s → background")
    logger.info("   • Email sending: 1-5s → background") 
    logger.info("   • File uploads: 1-3s → background")
    logger.info("   • Database writes → background")
    logger.info("🎯 Expected contract signing time: 100-500ms")
    
    try:
        run_worker(WorkerSettings)
    except KeyboardInterrupt:
        logger.info("👋 Worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        raise