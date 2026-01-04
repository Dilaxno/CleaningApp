import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL

logger = logging.getLogger(__name__)

# Configure engine with SSL and connection pooling settings for Neon
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Test connections before using
        pool_recycle=300,    # Recycle connections every 5 minutes
        pool_size=5,
        max_overflow=10,
    )
    logger.info("✅ Database engine created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create database engine: {e}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
