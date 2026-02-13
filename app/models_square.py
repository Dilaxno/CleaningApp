"""
Square Integration Models
Database models for storing Square OAuth tokens and payment data
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text

from .database import Base


class SquareIntegration(Base):
    """Store Square OAuth tokens and merchant information"""

    __tablename__ = "square_integrations"

    user_id = Column(String, primary_key=True, index=True)
    merchant_id = Column(String, nullable=False)
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
