#!/usr/bin/env python3
"""
Database optimization script for CleaningApp
Adds missing indexes and optimizes slow queries
"""

import logging
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_indexes(engine):
    """Create missing indexes for performance optimization"""
    
    indexes_to_create = [
        # User table optimizations (removed CONCURRENTLY for transaction compatibility)
        "CREATE INDEX IF NOT EXISTS idx_users_email_verified ON users(email_verified) WHERE email_verified = true;",
        "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan);",
        "CREATE INDEX IF NOT EXISTS idx_users_subscription_status ON users(subscription_status);",
        
        # Client table optimizations
        "CREATE INDEX IF NOT EXISTS idx_clients_user_id_status ON clients(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_clients_created_at ON clients(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);",
        
        # Contract table optimizations
        "CREATE INDEX IF NOT EXISTS idx_contracts_user_id_status ON contracts(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_contracts_client_id_status ON contracts(client_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_contracts_created_at ON contracts(created_at);",
        
        # Invoice table optimizations (likely cause of 6.45s query)
        "CREATE INDEX IF NOT EXISTS idx_invoices_user_id_status ON invoices(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_invoices_contract_id ON invoices(contract_id);",
        "CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);",
        "CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);",
        
        # Schedule table optimizations
        "CREATE INDEX IF NOT EXISTS idx_schedules_user_id_status ON schedules(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_client_id ON schedules(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_scheduled_date ON schedules(scheduled_date);",
        
        # Business config optimizations (correct table name)
        "CREATE INDEX IF NOT EXISTS idx_business_configs_user_id ON business_configs(user_id);",
        
        # Template customization optimizations
        "CREATE INDEX IF NOT EXISTS idx_user_template_customization_user_active ON user_template_customizations(user_id, is_active) WHERE is_active = true;",
    ]
    
    # Create indexes one at a time with individual connections to avoid transaction issues
    for index_sql in indexes_to_create:
        try:
            # Use a fresh connection for each index to avoid transaction errors
            with engine.connect() as conn:
                conn = conn.execution_options(autocommit=True)
                logger.info(f"Creating index: {index_sql[:80]}...")
                conn.execute(text(index_sql))
                logger.info("✅ Index created successfully")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("ℹ️ Index already exists, skipping")
            elif "does not exist" in str(e).lower():
                logger.warning(f"⚠️ Table does not exist, skipping: {index_sql[:80]}...")
            else:
                logger.error(f"❌ Failed to create index: {e}")

def analyze_tables(engine):
    """Run ANALYZE on all tables to update statistics"""
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Use autocommit mode for ANALYZE commands
    with engine.connect() as conn:
        conn = conn.execution_options(autocommit=True)
        
        for table in tables:
            try:
                logger.info(f"Analyzing table: {table}")
                conn.execute(text(f"ANALYZE {table};"))
            except Exception as e:
                logger.error(f"❌ Failed to analyze table {table}: {e}")

def optimize_database():
    """Main optimization function"""
    logger.info("🚀 Starting database optimization...")
    
    try:
        engine = create_engine(DATABASE_URL)
        logger.info("✅ Connected to database")
        
        # Create missing indexes
        logger.info("📊 Creating performance indexes...")
        create_indexes(engine)
        
        # Update table statistics
        logger.info("📈 Updating table statistics...")
        analyze_tables(engine)
        
        logger.info("🎉 Database optimization completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Database optimization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    optimize_database()