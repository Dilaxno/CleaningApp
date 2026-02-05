#!/usr/bin/env python3
"""
Performance Diagnostic Script
Checks database indexes, connection pool, and query performance
"""

import logging
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_indexes(engine):
    """Check which indexes exist on important tables"""
    logger.info("\n📊 Checking Database Indexes")
    logger.info("=" * 60)
    
    important_tables = ['users', 'clients', 'contracts', 'invoices', 'schedules']
    inspector = inspect(engine)
    
    for table in important_tables:
        try:
            indexes = inspector.get_indexes(table)
            logger.info(f"\n📋 Table: {table}")
            logger.info(f"   Indexes: {len(indexes)}")
            for idx in indexes:
                cols = ', '.join(idx['column_names'])
                logger.info(f"   • {idx['name']}: ({cols})")
        except Exception as e:
            logger.error(f"   ❌ Error checking {table}: {e}")

def check_table_stats(engine):
    """Check table sizes and row counts"""
    logger.info("\n📈 Table Statistics")
    logger.info("=" * 60)
    
    with engine.connect() as conn:
        # Get table sizes
        result = conn.execute(text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 10;
        """))
        
        logger.info(f"\n{'Table':<30} {'Size':<15} {'Rows':<15}")
        logger.info("-" * 60)
        for row in result:
            logger.info(f"{row.tablename:<30} {row.size:<15} {row.row_count:<15}")

def check_slow_queries(engine):
    """Check for slow queries if pg_stat_statements is enabled"""
    logger.info("\n🐌 Checking for Slow Queries")
    logger.info("=" * 60)
    
    try:
        with engine.connect() as conn:
            # Check if pg_stat_statements is available
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                ) as has_extension;
            """))
            
            has_extension = result.fetchone()[0]
            
            if not has_extension:
                logger.warning("⚠️  pg_stat_statements extension not enabled")
                logger.info("   To enable: CREATE EXTENSION pg_stat_statements;")
                return
            
            # Get slow queries
            result = conn.execute(text("""
                SELECT 
                    substring(query, 1, 100) as short_query,
                    calls,
                    round(total_exec_time::numeric, 2) as total_time_ms,
                    round(mean_exec_time::numeric, 2) as avg_time_ms,
                    round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) as pct
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_exec_time DESC
                LIMIT 10;
            """))
            
            logger.info(f"\n{'Query':<50} {'Calls':<10} {'Avg (ms)':<12} {'% Time':<10}")
            logger.info("-" * 90)
            for row in result:
                logger.info(f"{row.short_query:<50} {row.calls:<10} {row.avg_time_ms:<12} {row.pct:<10}")
                
    except Exception as e:
        logger.warning(f"⚠️  Could not check slow queries: {e}")

def check_connection_pool(engine):
    """Check database connection pool status"""
    logger.info("\n🔌 Connection Pool Status")
    logger.info("=" * 60)
    
    pool = engine.pool
    logger.info(f"Pool size: {pool.size()}")
    logger.info(f"Checked out connections: {pool.checkedout()}")
    logger.info(f"Overflow: {pool.overflow()}")
    logger.info(f"Checked in: {pool.checkedin()}")

def check_missing_indexes(engine):
    """Check for missing indexes that could improve performance"""
    logger.info("\n🔍 Checking for Missing Indexes")
    logger.info("=" * 60)
    
    recommended_indexes = {
        'users': ['email_verified', 'plan', 'subscription_status'],
        'clients': ['user_id', 'status', 'email'],
        'contracts': ['user_id', 'client_id', 'status'],
        'invoices': ['user_id', 'client_id', 'contract_id', 'status', 'due_date'],
        'schedules': ['user_id', 'client_id', 'status', 'scheduled_date'],
    }
    
    inspector = inspect(engine)
    
    for table, columns in recommended_indexes.items():
        try:
            existing_indexes = inspector.get_indexes(table)
            existing_cols = set()
            for idx in existing_indexes:
                existing_cols.update(idx['column_names'])
            
            missing = [col for col in columns if col not in existing_cols]
            
            if missing:
                logger.warning(f"⚠️  {table}: Missing indexes on {', '.join(missing)}")
            else:
                logger.info(f"✅ {table}: All recommended indexes present")
                
        except Exception as e:
            logger.error(f"❌ Error checking {table}: {e}")

def run_diagnostics():
    """Run all diagnostic checks"""
    logger.info("\n" + "=" * 60)
    logger.info("🔍 CleaningApp Performance Diagnostics")
    logger.info("=" * 60)
    
    try:
        engine = create_engine(DATABASE_URL)
        logger.info("✅ Connected to database")
        
        check_connection_pool(engine)
        check_indexes(engine)
        check_missing_indexes(engine)
        check_table_stats(engine)
        check_slow_queries(engine)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Diagnostics completed")
        logger.info("=" * 60)
        
        logger.info("\n💡 Recommendations:")
        logger.info("   1. Run 'sudo python3 optimize_database.py' to create missing indexes")
        logger.info("   2. Enable pg_stat_statements for better query monitoring")
        logger.info("   3. Monitor slow queries with: sudo journalctl -u cleaningapp -f | grep 'Slow query'")
        logger.info("   4. Consider adding Redis caching for frequently accessed data")
        
    except Exception as e:
        logger.error(f"❌ Diagnostics failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_diagnostics()
