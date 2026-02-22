import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


def generate_public_id():
    """Generate a unique public ID for secure public access"""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)  # Email verification status
    pending_email = Column(String(255), nullable=True)  # Pending new email during email change
    verification_otp = Column(String(10), nullable=True)  # Current OTP for email verification
    otp_expires_at = Column(DateTime, nullable=True)  # OTP expiration time
    profile_picture_url = Column(String(500), nullable=True)  # R2 key for profile picture
    default_brand_color = Column(String(7), nullable=True)  # e.g., #RRGGBB
    account_type = Column(String(50), nullable=True)
    hear_about = Column(String(100), nullable=True)
    plan = Column(String(50), nullable=True)  # team, enterprise - null until user selects
    # Dodo subscription identifier for this user's active subscription; used for change/cancel flows
    subscription_id = Column(String(255), nullable=True)
    subscription_start_date = Column(
        DateTime, nullable=True
    )  # When subscription started (for billing cycle)
    billing_cycle = Column(
        String(20), nullable=True
    )  # monthly, yearly - tracks subscription interval
    last_payment_date = Column(DateTime, nullable=True)  # Last successful payment date for renewals
    next_billing_date = Column(DateTime, nullable=True)  # Next scheduled billing date
    subscription_status = Column(
        String(50), default="active", nullable=True
    )  # active, past_due, cancelled
    clients_this_month = Column(
        Integer, default=0, nullable=False
    )  # Counter for monthly client limit
    month_reset_date = Column(
        DateTime, nullable=True
    )  # Track when to reset the counter (30 days from subscription date)
    onboarding_completed = Column(Boolean, default=False)
    # Two-Factor Authentication fields
    totp_secret = Column(String(100), nullable=True)  # TOTP secret for authenticator app
    totp_enabled = Column(Boolean, default=False, nullable=False)  # Is TOTP enabled
    phone_number = Column(String(50), nullable=True)  # Phone number for SMS 2FA
    phone_verified = Column(Boolean, default=False, nullable=False)  # Is phone verified
    phone_2fa_enabled = Column(Boolean, default=False, nullable=False)  # Is SMS 2FA enabled
    recovery_email = Column(String(255), nullable=True)  # Secondary email for recovery
    recovery_email_verified = Column(
        Boolean, default=False, nullable=False
    )  # Is recovery email verified
    backup_codes = Column(JSON, default=list, nullable=True)  # Encrypted backup codes
    # Notification preferences
    notify_new_clients = Column(
        Boolean, default=True, nullable=False
    )  # Email when new client submits form
    notify_contract_signed = Column(
        Boolean, default=True, nullable=False
    )  # Email when contract is signed
    notify_schedule_confirmed = Column(
        Boolean, default=True, nullable=False
    )  # Email when schedule is confirmed
    notify_payment_received = Column(
        Boolean, default=True, nullable=False
    )  # Email when payment is received
    notify_reminders = Column(
        Boolean, default=True, nullable=False
    )  # Email for upcoming appointments
    notify_marketing = Column(
        Boolean, default=False, nullable=False
    )  # Marketing and product updates
    # Payment notification tracking
    unread_payments_count = Column(
        Integer, default=0, nullable=False
    )  # Count of unread payment notifications
    last_payment_check = Column(DateTime, nullable=True)  # Last time user checked payments
    # Payout information
    payout_country = Column(String(2), nullable=True)  # ISO country code (e.g., "US", "GB", "FR")
    payout_currency = Column(String(3), nullable=True)  # Currency code (e.g., "USD", "EUR", "GBP")
    payout_account_holder_name = Column(String(255), nullable=True)  # Account holder name
    payout_bank_name = Column(String(255), nullable=True)  # Bank name
    payout_account_number = Column(
        String(50), nullable=True
    )  # Account number (encrypted in production)
    payout_routing_number = Column(String(50), nullable=True)  # Routing/Sort code (US/UK)
    payout_iban = Column(String(50), nullable=True)  # IBAN (Europe)
    payout_swift_bic = Column(String(20), nullable=True)  # SWIFT/BIC code
    payout_bank_address = Column(
        String(500), nullable=True
    )  # Bank address (for international transfers)

    # Dodo Payments linkage (non-PCI metadata only)
    dodo_customer_id = Column(String(255), nullable=True)
    dodo_default_payment_method_id = Column(String(255), nullable=True)
    dodo_payment_method_brand = Column(String(50), nullable=True)
    dodo_payment_method_last4 = Column(String(4), nullable=True)
    dodo_payment_method_exp_month = Column(Integer, nullable=True)
    dodo_payment_method_exp_year = Column(Integer, nullable=True)
    dodo_payment_method_type = Column(String(50), nullable=True)

    # Billing address from checkout (non-sensitive PII)
    billing_street = Column(String(500), nullable=True)
    billing_city = Column(String(255), nullable=True)
    billing_state = Column(String(255), nullable=True)
    billing_zipcode = Column(String(20), nullable=True)
    billing_country = Column(String(2), nullable=True)  # ISO country code
    billing_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    business_config = relationship("BusinessConfig", back_populates="user", uselist=False)
    clients = relationship("Client", back_populates="user")
    contracts = relationship("Contract", back_populates="user")
    schedules = relationship("Schedule", back_populates="user")
    form_templates = relationship("FormTemplate", back_populates="user")


class BusinessConfig(Base):
    __tablename__ = "business_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # Branding
    business_name = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    brand_color = Column(String(7), nullable=True)  # Hex color code for brand (e.g., #00C4B4)
    signature_url = Column(String(500), nullable=True)
    onboarding_complete = Column(Boolean, default=False)
    form_embedding_enabled = Column(
        Boolean, default=False
    )  # Whether owner wants iframe embedding for full automation
    pricing_model = Column(String(50), nullable=True)  # sqft, room, hourly, flat
    meetings_required = Column(
        Boolean, default=False
    )  # Whether client meetings are required before confirmation
    payment_handling = Column(
        String(20), nullable=True
    )  # "manual" or "automatic" - how provider handles payments
    cancellation_window = Column(Integer, default=24)  # Hours notice required for cancellation

    # Availability settings
    working_days = Column(
        JSON, nullable=True
    )  # e.g., ["monday", "tuesday", "wednesday", "thursday", "friday"]
    working_hours = Column(JSON, nullable=True)  # e.g., {"start": "09:00", "end": "17:00"}
    break_times = Column(JSON, nullable=True)  # e.g., [{"start": "12:00", "end": "13:00"}]
    day_schedules = Column(
        JSON, nullable=True
    )  # Per-day working hours: {"monday": {"enabled": true, "startTime": "09:00", "endTime": "17:00"}, ...}
    off_work_periods = Column(
        JSON, nullable=True
    )  # Off-work periods: [{"id": "...", "name": "Vacation", "startDate": "2026-01-15", "endDate": "2026-01-20", "allDay": true, ...}]
    custom_addons = Column(
        JSON, nullable=True
    )  # Custom add-on services: [{"id": "...", "name": "Oven cleaning", "price": "25", "pricingMetric": "per service"}]
    supplies_provided = Column(String(20), nullable=True)  # "provider" or "client"
    available_supplies = Column(JSON, nullable=True)  # List of supply IDs the provider brings
    rate_per_sqft = Column(Float, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    hourly_rate_mode = Column(String(20), default="per_cleaner")  # per_cleaner or general
    flat_rate = Column(Float, nullable=True)
    # Flat fee by job size (used when pricing_model == "flat")
    flat_rate_small = Column(Float, nullable=True)
    flat_rate_medium = Column(Float, nullable=True)
    flat_rate_large = Column(Float, nullable=True)
    minimum_charge = Column(Float, nullable=True)
    # Legacy field - kept for backward compatibility
    cleaning_time_per_sqft = Column(Integer, nullable=True)
    # New three-category time estimation system
    time_small_job = Column(Float, nullable=True)  # Hours for jobs under 1,000 sqft
    time_medium_job = Column(Float, nullable=True)  # Hours for jobs 1,500-2,500 sqft
    time_large_job = Column(Float, nullable=True)  # Hours for jobs 2,500+ sqft
    cleaners_small_job = Column(Integer, default=1)
    cleaners_large_job = Column(Integer, default=2)
    buffer_time = Column(Integer, default=30)
    premium_evening_weekend = Column(Float, nullable=True)
    premium_deep_clean = Column(Float, nullable=True)
    discount_weekly = Column(Float, nullable=True)
    discount_biweekly = Column(Float, nullable=True)
    discount_monthly = Column(Float, nullable=True)
    discount_long_term = Column(Float, nullable=True)
    # First cleaning discount (applied only to the first cleaning session)
    first_cleaning_discount_type = Column(String(20), nullable=True)  # percent | fixed
    first_cleaning_discount_value = Column(Float, nullable=True)
    addon_windows = Column(Float, nullable=True)
    addon_carpets = Column(Float, nullable=True)  # Legacy per sq ft pricing - deprecated
    addon_carpet_small = Column(Float, nullable=True)  # Small carpet pricing
    addon_carpet_medium = Column(Float, nullable=True)  # Medium carpet pricing
    addon_carpet_large = Column(Float, nullable=True)  # Large carpet pricing
    payment_due_days = Column(Integer, default=15)
    late_fee_percent = Column(Float, default=1.5)
    standard_inclusions = Column(JSON, default=list)
    standard_exclusions = Column(JSON, default=list)
    custom_inclusions = Column(JSON, default=list)  # Custom user-added inclusions
    custom_exclusions = Column(JSON, default=list)  # Custom user-added exclusions
    preferred_units = Column(String(20), default="sqft")

    # Custom packages for "packages" pricing model
    custom_packages = Column(
        JSON, nullable=True
    )  # Custom packages: [{"id": "uuid", "name": "Full Deep Clean", "description": "...", "included": ["..."], "duration": 120, "priceType": "flat|range|quote", "price": 150, "priceMin": 100, "priceMax": 200}]

    # Custom forms domain (white-labeled public form links)
    # Example: forms.cleaningco.com (CNAME forms -> api.cleanenroll.com)
    custom_forms_domain = Column(String(255), nullable=True)

    # Accepted frequencies and payment methods
    accepted_frequencies = Column(
        JSON,
        default=[
            "daily",
            "2x-per-week",
            "3x-per-week",
            "weekly",
            "bi-weekly",
            "monthly",
        ],
    )  # Array of accepted cleaning frequencies
    accepted_payment_methods = Column(
        JSON, default=list
    )  # Array of accepted payment methods (cash, check, card, venmo, paypal, zelle, bank-transfer, square)

    # Custom SMTP settings (standard SMTP, not Resend)
    smtp_email = Column(String(255), nullable=True)  # e.g., bookings@preclean.com
    smtp_host = Column(String(255), nullable=True)  # e.g., smtp.gmail.com
    smtp_port = Column(Integer, default=587)  # 587 for TLS, 465 for SSL
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(String(500), nullable=True)  # Encrypted
    smtp_use_tls = Column(Boolean, default=True)
    smtp_status = Column(String(50), nullable=True)  # live, testing, failed
    smtp_last_test_at = Column(DateTime, nullable=True)
    smtp_last_test_success = Column(Boolean, nullable=True)
    smtp_error_message = Column(String(500), nullable=True)

    # Subdomain verification for automated emails
    email_subdomain = Column(String(255), nullable=True)  # e.g., mail.preclean.com
    subdomain_verification_status = Column(String(50), nullable=True)  # pending, verified, failed
    subdomain_dns_records = Column(JSON, nullable=True)  # Required DNS records for verification
    subdomain_verified_at = Column(DateTime, nullable=True)
    subdomain_last_check_at = Column(DateTime, nullable=True)
    subdomain_verification_token = Column(String(255), nullable=True)  # Unique token for TXT record

    # Service areas configuration
    service_areas = Column(
        JSON, default=list
    )  # List of service areas with states, counties, neighborhoods

    # Active templates - list of template IDs that the business owner has selected to work with
    active_templates = Column(
        JSON, default=list
    )  # List of template IDs: ["office", "retail", "medical", ...]

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="business_config")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    # Public UUID for secure public access (prevents enumeration)
    # nullable=True initially to support existing records without UUIDs
    # Run add_contract_client_public_ids.py migration to populate existing records
    public_id = Column(
        String(36), unique=True, nullable=True, index=True, default=generate_public_id
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    property_type = Column(String(100), nullable=True)
    property_size = Column(Integer, nullable=True)
    frequency = Column(String(50), nullable=True)
    status = Column(String(50), default="pending")
    notes = Column(String(1000), nullable=True)
    form_data = Column(JSON, nullable=True)  # Store structured form submission data

    # Quote approval workflow fields
    quote_status = Column(
        String(50), default="pending_review"
    )  # pending_review, approved, adjusted, rejected
    quote_submitted_at = Column(DateTime, nullable=True)  # When client approved the automated quote
    quote_approved_at = Column(DateTime, nullable=True)  # When provider approved/adjusted
    quote_approved_by = Column(String(255), nullable=True)  # User ID who approved
    original_quote_amount = Column(Float, nullable=True)  # Original automated quote
    adjusted_quote_amount = Column(Float, nullable=True)  # Adjusted amount if changed
    quote_adjustment_notes = Column(String(5000), nullable=True)  # Provider's adjustment notes

    # Pending contract fields - stored until client completes signing and scheduling
    pending_contract_title = Column(String(255), nullable=True)
    pending_contract_description = Column(String(2000), nullable=True)
    pending_contract_type = Column(String(100), nullable=True)
    pending_contract_start_date = Column(DateTime, nullable=True)
    pending_contract_end_date = Column(DateTime, nullable=True)
    pending_contract_total_value = Column(Float, nullable=True)
    pending_contract_payment_terms = Column(String(255), nullable=True)
    pending_contract_terms_conditions = Column(String(5000), nullable=True)

    # Square subscription tracking (for recurring services)
    square_subscription_id = Column(String(255), nullable=True)  # Square subscription ID
    subscription_status = Column(String(50), nullable=True)  # active, paused, cancelled
    subscription_frequency = Column(String(50), nullable=True)  # weekly, bi-weekly, monthly

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="clients")
    contracts = relationship("Contract", back_populates="client", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="client", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="client", cascade="all, delete-orphan")
    scheduling_proposals = relationship(
        "SchedulingProposal", back_populates="client", cascade="all, delete-orphan"
    )
    quote_history = relationship(
        "QuoteHistory", back_populates="client", cascade="all, delete-orphan"
    )


class QuoteHistory(Base):
    """Audit trail for quote approval workflow"""

    __tablename__ = "quote_history"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    action = Column(String(50), nullable=False)  # submitted, approved, adjusted, rejected
    amount = Column(Float, nullable=True)
    notes = Column(String(5000), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="quote_history")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    # Public UUID for secure public access (prevents enumeration)
    # nullable=True initially to support existing records without UUIDs
    # Run add_contract_client_public_ids.py migration to populate existing records
    public_id = Column(
        String(36), unique=True, nullable=True, index=True, default=generate_public_id
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=True)
    contract_type = Column(String(100), nullable=True)  # recurring, maintenance
    # Status workflow: new → signed → active → completed/cancelled
    # new: Initial contract sent to client for signature
    # signed: Contract signed by both provider and client
    # active: First schedule date has arrived, service in progress (automatic transition)
    # cancelled: Owner manually cancelled the contract (manual only)
    # completed: Contract term finished (automatic transition when end_date passes)
    status = Column(String(50), default="new")
    client_onboarding_status = Column(
        String(50), default="pending_signature"
    )  # pending_signature, pending_scheduling, completed
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    total_value = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")  # Currency code
    payment_terms = Column(String(255), nullable=True)
    terms_conditions = Column(String(5000), nullable=True)
    pdf_key = Column(String(500), nullable=True)  # R2 key for the contract PDF
    pdf_hash = Column(String(64), nullable=True)  # SHA-256 hash of the PDF for integrity
    # Provider signature audit trail
    provider_signature = Column(String(100000), nullable=True)  # Base64 signature image
    signed_at = Column(DateTime, nullable=True)
    signature_ip = Column(String(45), nullable=True)  # IPv4 or IPv6
    signature_user_agent = Column(String(500), nullable=True)
    signature_timestamp = Column(DateTime, nullable=True)
    # Client signature audit trail
    client_signature = Column(String(100000), nullable=True)  # Base64 signature image
    client_signature_ip = Column(String(45), nullable=True)
    client_signature_user_agent = Column(String(500), nullable=True)
    client_signature_timestamp = Column(DateTime, nullable=True)
    # Legal
    jurisdiction = Column(String(255), nullable=True)  # e.g., "State of California, USA"

    # Revision request system
    revision_requested = Column(Boolean, default=False)  # True if provider requested changes
    revision_type = Column(String(50), nullable=True)  # 'pricing', 'scope', 'both'
    revision_notes = Column(String(2000), nullable=True)  # Provider's notes about requested changes
    revision_requested_at = Column(DateTime, nullable=True)
    revision_count = Column(Integer, default=0)  # Track number of revision rounds
    custom_quote = Column(
        JSON, nullable=True
    )  # Provider's custom pricing if different from auto-quote
    custom_scope = Column(JSON, nullable=True)  # Provider's custom scope (inclusions/exclusions)

    # Square payment integration
    square_invoice_id = Column(String(255), nullable=True)  # Square invoice ID (deposit invoice)
    square_invoice_url = Column(Text, nullable=True)  # Public Square payment URL (deposit)
    square_payment_status = Column(String(50), nullable=True)  # pending, paid, failed, cancelled
    square_invoice_created_at = Column(DateTime, nullable=True)  # When invoice was created

    # Deposit tracking (50% upfront payment)
    deposit_amount = Column(Float, nullable=True)  # 50% deposit amount
    deposit_paid = Column(Boolean, default=False)  # Whether deposit has been paid
    deposit_paid_at = Column(DateTime, nullable=True)  # When deposit was paid
    remaining_balance = Column(Float, nullable=True)  # Remaining 50% balance
    balance_invoice_id = Column(String(255), nullable=True)  # Square invoice ID for balance
    balance_invoice_url = Column(Text, nullable=True)  # Payment URL for balance invoice
    balance_paid = Column(Boolean, default=False)  # Whether balance has been paid
    balance_paid_at = Column(DateTime, nullable=True)  # When balance was paid

    # Square subscription integration (for recurring services)
    square_subscription_id = Column(String(255), nullable=True)  # Square subscription ID
    square_subscription_status = Column(String(50), nullable=True)  # active, paused, cancelled
    square_subscription_created_at = Column(
        DateTime, nullable=True
    )  # When subscription was created
    frequency = Column(String(50), nullable=True)  # weekly, bi-weekly, monthly, etc.

    # Payment tracking
    square_payment_received_at = Column(DateTime, nullable=True)  # When payment was received
    payment_confirmation_pending = Column(Boolean, default=False)  # Frontend redirect flag
    payment_confirmed_at = Column(DateTime, nullable=True)  # When payment was confirmed via webhook

    # Enhanced signature tracking
    provider_signed_at = Column(DateTime, nullable=True)  # When provider signed
    both_parties_signed_at = Column(DateTime, nullable=True)  # When both parties signed
    invoice_auto_generated = Column(Boolean, default=False)  # Whether invoice was auto-generated

    invoice_auto_sent = Column(Boolean, default=False)  # Whether Square invoice was auto-sent

    # Scope of Work (Exhibit A)
    scope_of_work = Column(JSON, nullable=True)  # Structured scope of work data
    exhibit_a_pdf_key = Column(String(500), nullable=True)  # R2 key for Exhibit A PDF
    invoice_auto_sent_at = Column(DateTime, nullable=True)  # When invoice was auto-sent

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="contracts")
    client = relationship("Client", back_populates="contracts")
    invoices = relationship("Invoice", back_populates="contract", cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="contract", cascade="all, delete-orphan")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    service_type = Column(String(100), nullable=True)  # standard, deep-clean, move-in, move-out
    scheduled_date = Column(DateTime, nullable=False)
    start_time = Column(String(10), nullable=True)  # HH:MM format
    end_time = Column(String(10), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    status = Column(String(50), default="scheduled")  # scheduled, in-progress, completed, cancelled
    approval_status = Column(String(50), default="pending")  # pending, accepted, change_requested
    proposed_date = Column(DateTime, nullable=True)  # Provider's proposed alternative date
    proposed_start_time = Column(String(10), nullable=True)  # Provider's proposed alternative start
    proposed_end_time = Column(String(10), nullable=True)  # Provider's proposed alternative end
    notes = Column(String(1000), nullable=True)
    address = Column(String(500), nullable=True)
    assigned_to = Column(String(255), nullable=True)  # cleaner name or team
    price = Column(Float, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)  # weekly, bi-weekly, monthly

    # Calendly integration fields
    calendly_event_uri = Column(String(500), nullable=True, index=True)  # Unique Calendly event URI
    calendly_event_id = Column(String(255), nullable=True)  # Calendly event UUID
    calendly_invitee_uri = Column(String(500), nullable=True)  # Invitee URI for tracking
    calendly_booking_method = Column(
        String(50), nullable=True
    )  # 'client_selected', 'provider_created', 'synced'
    location = Column(String(500), nullable=True)  # Event location (separate from address)

    # Google Calendar integration fields
    google_calendar_event_id = Column(
        String(500), nullable=True, index=True
    )  # Google Calendar event ID

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="schedules")
    client = relationship("Client", back_populates="schedules")


class SchedulingProposal(Base):
    __tablename__ = "scheduling_proposals"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        String(50), default="pending"
    )  # pending, accepted, rejected, countered, expired
    proposal_round = Column(Integer, default=1)
    proposed_by = Column(String(50), nullable=False)  # provider or client
    time_slots = Column(JSON, nullable=False)  # Array of time slot objects
    selected_slot_date = Column(DateTime, nullable=True)
    selected_slot_start_time = Column(String(10), nullable=True)
    selected_slot_end_time = Column(String(10), nullable=True)
    preferred_days = Column(String(50), nullable=True)
    preferred_time_window = Column(String(50), nullable=True)
    client_notes = Column(String(1000), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="scheduling_proposals")


class IntegrationRequest(Base):
    __tablename__ = "integration_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who submitted the request
    name = Column(String(255), nullable=False)  # Integration name (e.g., "QuickBooks")
    logo_url = Column(
        String(2000), nullable=False
    )  # URL or R2 key for the logo (increased for long URLs)
    integration_type = Column(
        String(100), nullable=False
    )  # accounting, crm, payment, scheduling, etc.
    use_case = Column(Text, nullable=False)  # Description of how it would be used
    upvotes = Column(Integer, default=1)  # Start with 1 (submitter's implicit vote)
    status = Column(
        String(50), default="pending"
    )  # pending, approved, in_progress, completed, rejected
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class IntegrationRequestVote(Base):
    __tablename__ = "integration_request_votes"

    id = Column(Integer, primary_key=True, index=True)
    integration_request_id = Column(Integer, ForeignKey("integration_requests.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Unique constraint to prevent duplicate votes
    __table_args__ = ({"sqlite_autoincrement": True},)


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(
        String(100), unique=True, index=True, nullable=False
    )  # e.g., "office", "retail"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for system templates
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # hex color
    is_system_template = Column(
        Boolean, default=False, nullable=False
    )  # true for pre-built templates
    is_active = Column(Boolean, default=True, nullable=False)
    template_data = Column(JSON, nullable=False)  # stores the complete template structure
    scope_template = Column(
        JSON, nullable=True
    )  # default scope of work template (service areas and tasks)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="form_templates")


class UserTemplateCustomization(Base):
    __tablename__ = "user_template_customizations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("form_templates.id"), nullable=False)
    customized_data = Column(JSON, nullable=False)  # stores user's customizations
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    template = relationship("FormTemplate")
