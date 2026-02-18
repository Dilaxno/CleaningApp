"""
Twilio Integration Models
Database models for storing Twilio credentials and SMS logs
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class TwilioIntegration(Base):
    """Store Twilio credentials and configuration"""

    __tablename__ = "twilio_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Twilio credentials (encrypted)
    account_sid = Column(Text, nullable=False)
    auth_token = Column(Text, nullable=False)
    messaging_service_sid = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)

    # Settings
    sms_enabled = Column(Boolean, default=True)
    send_estimate_approval = Column(Boolean, default=True)
    send_schedule_confirmation = Column(Boolean, default=True)
    send_contract_signed = Column(Boolean, default=True)
    send_job_reminder = Column(Boolean, default=True)
    send_job_completion = Column(Boolean, default=True)
    send_payment_confirmation = Column(Boolean, default=True)

    # Status
    is_verified = Column(Boolean, default=False)
    last_test_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User")


class TwilioSMSLog(Base):
    """Track SMS messages sent via Twilio"""

    __tablename__ = "twilio_sms_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    integration_id = Column(Integer, ForeignKey("twilio_integrations.id"), nullable=False)

    # Message details
    to_phone = Column(String(20), nullable=False)
    message_body = Column(Text, nullable=False)
    message_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)

    # Twilio response
    twilio_message_sid = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User")
    integration = relationship("TwilioIntegration")
