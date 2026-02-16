import logging
import os
import time

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

# Get environment-specific pool settings
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))
ENABLE_QUERY_LOGGING = os.getenv("DB_LOG_SLOW_QUERIES", "true").lower() == "true"
SLOW_QUERY_THRESHOLD = float(os.getenv("DB_SLOW_QUERY_THRESHOLD", "1.0"))

# Configure engine with optimized connection pooling for scale
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Test connections before using
        pool_recycle=POOL_RECYCLE,  # Recycle connections every 5 minutes
        pool_size=POOL_SIZE,  # Base pool size (20 for production)
        max_overflow=MAX_OVERFLOW,  # Overflow connections (30 for production)
        pool_timeout=POOL_TIMEOUT,  # Wait 30s for connection
        echo=False,  # Don't log all SQL (use slow query logging instead)
    )
    logger.info("✅ Database engine created successfully")
    logger.info(
        f"📊 Connection pool: size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}, timeout={POOL_TIMEOUT}s"
    )
except Exception as e:
    logger.error(f"❌ Failed to create database engine: {e}")
    raise

# Slow query logging for performance monitoring
if ENABLE_QUERY_LOGGING:

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, _cursor, statement, _parameters, context, _executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, _cursor, statement, _parameters, context, _executemany):
        total = time.time() - conn.info["query_start_time"].pop(-1)
        if total > SLOW_QUERY_THRESHOLD:
            # Log slow queries for optimization
            logger.warning(f"🐌 Slow query ({total:.2f}s): {statement[:200]}...")

    logger.info(f"📊 Slow query logging enabled (threshold: {SLOW_QUERY_THRESHOLD}s)")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
