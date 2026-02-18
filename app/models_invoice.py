"""
Invoice and Payment Models for Client Invoicing System
"""

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


def generate_public_id():
    """Generate a unique public ID for secure public access"""
    return str(uuid.uuid4())


class Invoice(Base):
    """Invoice model for client billing"""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    # Public UUID for secure public access (prevents enumeration)
    # nullable=True initially to support existing records without UUIDs
    # Run add_invoice_public_id.py migration to populate existing records
    public_id = Column(
        String(36), unique=True, nullable=True, index=True, default=generate_public_id
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Service provider
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True)

    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    service_type = Column(String(100), nullable=True)  # one-time, weekly, bi-weekly, monthly
    base_amount = Column(Float, nullable=False)  # Base service rate
    frequency_discount = Column(Float, default=0)  # Discount for recurring
    addon_amount = Column(Float, default=0)  # Additional services
    tax_amount = Column(Float, default=0)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")

    # Recurring billing
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)  # weekly, bi-weekly, monthly
    billing_interval = Column(String(20), nullable=True)  # day, week, month, year
    billing_interval_count = Column(Integer, default=1)

    # Status
    status = Column(String(50), default="pending")  # pending, sent, paid, overdue, cancelled

    # Dodo Payments integration
    dodo_product_id = Column(
        String(255), nullable=True
    )  # Adhoc product ID (shared across all invoices)
    dodo_payment_link = Column(String(500), nullable=True)  # Checkout URL
    dodo_payment_id = Column(String(255), nullable=True)  # Payment ID after completion

    # PDF
    pdf_key = Column(String(500), nullable=True)  # R2 key for invoice PDF

    # Dates
    issue_date = Column(DateTime, server_default=func.now())
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="invoices")
    contract = relationship("Contract", back_populates="invoices")
    visit = relationship("Visit", back_populates="invoice", uselist=False)


class Payout(Base):
    """Payout tracking for service providers"""

    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Service provider

    # Payout details
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(50), default="pending")  # pending, processing, completed, failed

    # Related invoices (JSON array of invoice IDs)
    invoice_ids = Column(JSON, default=list)

    # Payout method
    payout_method = Column(String(50), nullable=True)  # bank_transfer, paypal, etc.
    payout_details = Column(JSON, nullable=True)  # Bank account info, etc.

    # Processing
    requested_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Reference
    reference_id = Column(String(255), nullable=True)  # External payout reference
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SubscriptionPayment(Base):
    """Track subscription payments charged to the platform user (provider) via Dodo"""

    __tablename__ = "subscription_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Dodo references
    dodo_payment_id = Column(String(255), unique=True, nullable=False, index=True)
    dodo_subscription_id = Column(String(255), nullable=True)
    dodo_customer_id = Column(String(255), nullable=True)

    # Amounts (store in major units for display; raw_lowest_unit stored for audit)
    amount = Column(Float, nullable=True)  # Converted to major unit (e.g., USD -> dollars)
    amount_lowest_unit = Column(Integer, nullable=True)  # Raw amount from Dodo (e.g., cents)
    currency = Column(String(10), default="USD")

    # Status and description
    status = Column(String(50), default="paid")  # paid, failed, pending
    description = Column(Text, nullable=True)  # e.g., plan name or invoice title
    invoice_number = Column(String(100), nullable=True)

    # Timestamps from provider
    paid_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
