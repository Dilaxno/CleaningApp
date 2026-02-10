"""
QuickBooks Integration Models
Database models for storing QuickBooks OAuth tokens and sync data
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class QuickBooksIntegration(Base):
    """Store QuickBooks OAuth tokens and company information"""
    __tablename__ = "quickbooks_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)

    # QuickBooks company info
    realm_id = Column(String(255), nullable=False)  # QuickBooks company ID
    company_name = Column(String(255), nullable=True)

    # Sync settings
    auto_sync_enabled = Column(Boolean, default=True)
    sync_invoices = Column(Boolean, default=True)
    sync_payments = Column(Boolean, default=True)
    sync_customers = Column(Boolean, default=True)
    
    # Last sync tracking
    last_invoice_sync = Column(DateTime, nullable=True)
    last_payment_sync = Column(DateTime, nullable=True)
    last_customer_sync = Column(DateTime, nullable=True)

    # Environment (sandbox or production)
    environment = Column(String(50), default="production")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User")


class QuickBooksSyncLog(Base):
    """Track QuickBooks sync operations"""
    __tablename__ = "quickbooks_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    integration_id = Column(Integer, ForeignKey("quickbooks_integrations.id"), nullable=False)
    
    sync_type = Column(String(50), nullable=False)  # invoice, payment, customer
    entity_type = Column(String(50), nullable=False)  # Contract, Invoice, Client
    entity_id = Column(Integer, nullable=False)
    
    quickbooks_id = Column(String(255), nullable=True)  # QuickBooks entity ID
    
    status = Column(String(50), nullable=False)  # success, failed, pending
    error_message = Column(Text, nullable=True)
    
    sync_data = Column(JSON, nullable=True)  # Store sync details
    
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User")
    integration = relationship("QuickBooksIntegration")
