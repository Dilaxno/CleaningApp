"""
Visit Management Models for Contract Execution
"""

import uuid

from sqlalchemy import ARRAY, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


def generate_public_id():
    """Generate a unique public ID for secure public access"""
    return str(uuid.uuid4())


class Visit(Base):
    """Visit model for tracking individual service visits within a contract"""

    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(
        String(36), unique=True, nullable=False, index=True, default=generate_public_id
    )

    # Relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)

    # Visit details
    visit_number = Column(Integer, nullable=False)  # Sequential number within contract
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Scheduling
    scheduled_date = Column(DateTime, nullable=False)
    scheduled_start_time = Column(String(10), nullable=True)  # HH:MM format
    scheduled_end_time = Column(String(10), nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Actual execution times
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)

    # Status workflow: scheduled → in_progress → completed → payment_processing → closed
    # scheduled: Visit is scheduled and upcoming
    # in_progress: Provider clicked "Start Job"
    # completed: Provider clicked "Mark as Complete"
    # payment_processing: Invoice created/payment captured, awaiting confirmation
    # closed: Payment confirmed and visit fully closed
    status = Column(String(50), default="scheduled", nullable=False, index=True)

    # Pricing
    visit_amount = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")

    # Payment tracking
    payment_method = Column(String(50), nullable=True)  # square, manual, etc.
    payment_status = Column(String(50), nullable=True)  # pending, paid, failed
    payment_captured_at = Column(DateTime, nullable=True)

    # Square integration
    square_invoice_id = Column(String(255), nullable=True)
    square_invoice_url = Column(Text, nullable=True)
    square_payment_id = Column(String(255), nullable=True)

    # Notes and tracking
    provider_notes = Column(Text, nullable=True)
    client_notes = Column(Text, nullable=True)
    completion_notes = Column(Text, nullable=True)

    # Photo proof of service (required for completion)
    photo_proof_urls = Column(ARRAY(Text), nullable=True)  # R2 URLs for photos (min 2, max 10)
    photo_count = Column(Integer, default=0, nullable=False)  # Number of photos uploaded
    photos_uploaded_at = Column(DateTime, nullable=True)  # When photos were uploaded

    # Audit trail
    started_by = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_by = Column(String(255), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contract = relationship("Contract", back_populates="visits")
    client = relationship("Client", back_populates="visits")
    invoice = relationship("Invoice", back_populates="visit", uselist=False)
