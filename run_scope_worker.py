"""
Scope Proposal Background Worker Runner
Run this as a separate process: python run_scope_worker.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.workers.scope_worker import run_scope_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("🚀 Starting Scope Proposal Background Worker...")
    try:
        asyncio.run(run_scope_worker())
    except KeyboardInterrupt:
        logger.info("👋 Scope worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Scope worker crashed: {e}")
        sys.exit(1)
