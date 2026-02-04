#!/usr/bin/env python3
"""
Simple index creation script for CleaningApp
Creates indexes one by one to avoid transaction issues
"""

import logging
import os
import sys
import psycopg
from urllib.parse import urlparse

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_indexes_simple():
    """Create indexes using direct psycopg connection to avoid transaction issues"""
    
    # Parse DATABASE_URL to get connection parameters
    parsed = urlparse(DATABASE_URL)
    
    # Connect directly with psycopg (no SQLAlchemy transactions)
    try:
        with psycopg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password,
            autocommit=True  # Enable autocommit to avoid transaction blocks
        ) as conn:
            
            indexes = [
                # Critical indexes for performance
                ("idx_invoices_user_id_status", "CREATE INDEX IF NOT EXISTS idx_invoices_user_id_status ON invoices(user_id, status);"),
                ("idx_invoices_client_id", "CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);"),
                ("idx_invoices_created_at", "CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);"),
                ("idx_clients_user_id_status", "CREATE INDEX IF NOT EXISTS idx_clients_user_id_status ON clients(user_id, status);"),
                ("idx_contracts_user_id_status", "CREATE INDEX IF NOT EXISTS idx_contracts_user_id_status ON contracts(user_id, status);"),
                ("idx_schedules_user_id_status", "CREATE INDEX IF NOT EXISTS idx_schedules_user_id_status ON schedules(user_id, status);"),
                ("idx_users_plan", "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan);"),
                ("idx_business_config_user_id", "CREATE INDEX IF NOT EXISTS idx_business_config_user_id ON business_config(user_id);"),
            ]
            
            logger.info("🚀 Creating critical performance indexes...")
            
            for index_name, index_sql in indexes:
                try:
                    logger.info(f"Creating {index_name}...")
                    with conn.cursor() as cur:
                        cur.execute(index_sql)
                    logger.info(f"✅ {index_name} created successfully")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"ℹ️ {index_name} already exists, skipping")
                    else:
                        logger.error(f"❌ Failed to create {index_name}: {e}")
            
            # Update table statistics
            logger.info("📊 Updating table statistics...")
            critical_tables = ['invoices', 'clients', 'contracts', 'users', 'schedules']
            
            for table in critical_tables:
                try:
                    logger.info(f"Analyzing {table}...")
                    with conn.cursor() as cur:
                        cur.execute(f"ANALYZE {table};")
                    logger.info(f"✅ {table} analyzed")
                except Exception as e:
                    logger.error(f"❌ Failed to analyze {table}: {e}")
            
            logger.info("🎉 Database optimization completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error("💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        sys.exit(1)

if __name__ == "__main__":
    create_indexes_simple()