#!/usr/bin/env python3
"""
Fix the business_configs index
"""

import logging
import psycopg
from urllib.parse import urlparse
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_business_config_index():
    """Create the missing business_configs index"""
    
    parsed = urlparse(DATABASE_URL)
    
    try:
        with psycopg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            autocommit=True
        ) as conn:
            
            logger.info("Creating business_configs index...")
            with conn.cursor() as cur:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_business_configs_user_id ON business_configs(user_id);")
            logger.info("✅ business_configs index created successfully")
            
    except Exception as e:
        logger.error(f"❌ Failed to create index: {e}")

if __name__ == "__main__":
    fix_business_config_index()