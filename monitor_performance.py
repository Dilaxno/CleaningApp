#!/usr/bin/env python3
"""
Performance monitoring script for CleaningApp
Monitors slow queries and provides optimization recommendations
"""

import logging
import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_slow_queries(engine):
    """Check for slow queries in PostgreSQL logs"""
    
    slow_query_sql = """
    SELECT 
        query,
        calls,
        total_time,
        mean_time,
        rows
    FROM pg_stat_statements 
    WHERE mean_time > 1000  -- queries taking more than 1 second on average
    ORDER BY mean_time DESC 
    LIMIT 10;
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(slow_query_sql))
            rows = result.fetchall()
            
            if rows:
                logger.warning("🐌 Found slow queries:")
                for row in rows:
                    logger.warning(f"  Mean time: {row[3]:.2f}ms, Calls: {row[1]}, Query: {row[0][:100]}...")
            else:
                logger.info("✅ No slow queries found")
                
    except Exception as e:
        logger.warning(f"⚠️ Could not check slow queries (pg_stat_statements may not be enabled): {e}")

def check_missing_indexes(engine):
    """Check for missing indexes on frequently queried columns"""
    
    missing_indexes_sql = """
    SELECT 
        schemaname,
        tablename,
        attname,
        n_distinct,
        correlation
    FROM pg_stats 
    WHERE schemaname = 'public' 
    AND n_distinct > 100  -- columns with many distinct values
    AND correlation < 0.1  -- low correlation (good for indexing)
    ORDER BY n_distinct DESC;
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(missing_indexes_sql))
            rows = result.fetchall()
            
            if rows:
                logger.info("📊 Columns that might benefit from indexes:")
                for row in rows:
                    logger.info(f"  {row[1]}.{row[2]} (distinct values: {row[3]})")
            else:
                logger.info("✅ No obvious missing indexes found")
                
    except Exception as e:
        logger.error(f"❌ Could not check missing indexes: {e}")

def check_table_sizes(engine):
    """Check table sizes to identify large tables"""
    
    table_sizes_sql = """
    SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
    FROM pg_tables 
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(table_sizes_sql))
            rows = result.fetchall()
            
            logger.info("📏 Table sizes:")
            for row in rows:
                logger.info(f"  {row[1]}: {row[2]}")
                
    except Exception as e:
        logger.error(f"❌ Could not check table sizes: {e}")

def check_connection_pool(engine):
    """Check connection pool status"""
    
    try:
        pool = engine.pool
        logger.info(f"🏊 Connection pool status:")
        logger.info(f"  Pool size: {pool.size()}")
        logger.info(f"  Checked out: {pool.checkedout()}")
        logger.info(f"  Overflow: {pool.overflow()}")
        logger.info(f"  Checked in: {pool.checkedin()}")
        
    except Exception as e:
        logger.error(f"❌ Could not check connection pool: {e}")

def monitor_performance():
    """Main monitoring function"""
    logger.info("🔍 Starting performance monitoring...")
    
    try:
        engine = create_engine(DATABASE_URL)
        logger.info("✅ Connected to database")
        
        # Check slow queries
        check_slow_queries(engine)
        
        # Check missing indexes
        check_missing_indexes(engine)
        
        # Check table sizes
        check_table_sizes(engine)
        
        # Check connection pool
        check_connection_pool(engine)
        
        logger.info("🎉 Performance monitoring completed!")
        
    except Exception as e:
        logger.error(f"❌ Performance monitoring failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    monitor_performance()