"""
Google Calendar Integration Models
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class GoogleCalendarIntegration(Base):
    __tablename__ = "google_calendar_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)

    # Google user info
    google_user_email = Column(String(255), nullable=True)
    google_calendar_id = Column(String(500), nullable=True)

    # Settings
    auto_sync_enabled = Column(Boolean, default=True)
    default_appointment_duration = Column(Integer, default=60)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User")
