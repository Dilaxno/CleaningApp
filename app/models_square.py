"""
Square integration models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from .database import Base


class SquareWebhookLog(Base):
    """Log of Square webhook events for debugging and audit"""
    __tablename__ = "square_webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(255), nullable=False)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    merchant_id = Column(String(255), nullable=True, index=True)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
