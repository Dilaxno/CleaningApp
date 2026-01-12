import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    account_type = Column(String(50), nullable=True)
    hear_about = Column(String(100), nullable=True)
    plan = Column(String(50), nullable=True)  # solo, team, enterprise - null until user selects
    # Dodo subscription identifier for this user's active subscription; used for change/cancel flows
    subscription_id = Column(String(255), nullable=True)
    subscription_start_date = Column(DateTime, nullable=True)  # When subscription started (for billing cycle)
    clients_this_month = Column(Integer, default=0, nullable=False)  # Counter for monthly client limit
    month_reset_date = Column(DateTime, nullable=True)  # Track when to reset the counter (30 days from subscription date)
    onboarding_completed = Column(Boolean, default=False)
    # Two-Factor Authentication fields
    totp_secret = Column(String(100), nullable=True)  # TOTP secret for authenticator app
    totp_enabled = Column(Boolean, default=False, nullable=False)  # Is TOTP enabled
    phone_number = Column(String(50), nullable=True)  # Phone number for SMS 2FA
    phone_verified = Column(Boolean, default=False, nullable=False)  # Is phone verified
    phone_2fa_enabled = Column(Boolean, default=False, nullable=False)  # Is SMS 2FA enabled
    recovery_email = Column(String(255), nullable=True)  # Secondary email for recovery
    recovery_email_verified = Column(Boolean, default=False, nullable=False)  # Is recovery email verified
    backup_codes = Column(JSON, default=list, nullable=True)  # Encrypted backup codes
    # Notification preferences
    notify_new_clients = Column(Boolean, default=True, nullable=False)  # Email when new client submits form
    notify_contract_signed = Column(Boolean, default=True, nullable=False)  # Email when contract is signed
    notify_schedule_confirmed = Column(Boolean, default=True, nullable=False)  # Email when schedule is confirmed
    notify_payment_received = Column(Boolean, default=True, nullable=False)  # Email when payment is received
    notify_reminders = Column(Boolean, default=True, nullable=False)  # Email for upcoming appointments
    notify_marketing = Column(Boolean, default=False, nullable=False)  # Marketing and product updates
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    business_config = relationship("BusinessConfig", back_populates="user", uselist=False)
    clients = relationship("Client", back_populates="user")
    contracts = relationship("Contract", back_populates="user")
    schedules = relationship("Schedule", back_populates="user")
    calendly_integration = relationship("CalendlyIntegration", back_populates="user", uselist=False)
    google_calendar_integration = relationship("GoogleCalendarIntegration", back_populates="user", uselist=False)


class BusinessConfig(Base):
    __tablename__ = "business_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # Branding
    business_name = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    signature_url = Column(String(500), nullable=True)
    onboarding_complete = Column(Boolean, default=False)
    pricing_model = Column(String(50), nullable=True)  # sqft, room, hourly, flat
    meetings_required = Column(Boolean, default=False)  # Whether client meetings are required before confirmation
    payment_handling = Column(String(20), nullable=True)  # "manual" or "automatic" - how provider handles payments
    cancellation_window = Column(Integer, default=24)  # Hours notice required for cancellation
    
    # Availability settings
    working_days = Column(JSON, nullable=True)  # e.g., ["monday", "tuesday", "wednesday", "thursday", "friday"]
    working_hours = Column(JSON, nullable=True)  # e.g., {"start": "09:00", "end": "17:00"}
    break_times = Column(JSON, nullable=True)  # e.g., [{"start": "12:00", "end": "13:00"}]
    day_schedules = Column(JSON, nullable=True)  # Per-day working hours: {"monday": {"enabled": true, "startTime": "09:00", "endTime": "17:00"}, ...}
    off_work_periods = Column(JSON, nullable=True)  # Off-work periods: [{"id": "...", "name": "Vacation", "startDate": "2026-01-15", "endDate": "2026-01-20", "allDay": true, ...}]
    custom_addons = Column(JSON, nullable=True)  # Custom add-on services: [{"id": "...", "name": "Oven cleaning", "price": "25", "pricingMetric": "per service"}]
    supplies_provided = Column(String(20), nullable=True)  # "provider" or "client"
    available_supplies = Column(JSON, nullable=True)  # List of supply IDs the provider brings
    rate_per_sqft = Column(Float, nullable=True)
    rate_per_room = Column(Float, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    flat_rate = Column(Float, nullable=True)
    minimum_charge = Column(Float, nullable=True)
    cleaning_time_per_sqft = Column(Integer, nullable=True)
    cleaners_small_job = Column(Integer, default=1)
    cleaners_large_job = Column(Integer, default=2)
    buffer_time = Column(Integer, default=30)
    premium_evening_weekend = Column(Float, nullable=True)
    premium_deep_clean = Column(Float, nullable=True)
    discount_weekly = Column(Float, nullable=True)
    discount_monthly = Column(Float, nullable=True)
    discount_long_term = Column(Float, nullable=True)
    addon_windows = Column(Float, nullable=True)
    addon_carpets = Column(Float, nullable=True)
    payment_due_days = Column(Integer, default=15)
    late_fee_percent = Column(Float, default=1.5)
    standard_inclusions = Column(JSON, default=list)
    standard_exclusions = Column(JSON, default=list)
    custom_inclusions = Column(JSON, default=list)  # Custom user-added inclusions
    custom_exclusions = Column(JSON, default=list)  # Custom user-added exclusions
    preferred_units = Column(String(20), default="sqft")
    
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="clients")
    contracts = relationship("Contract", back_populates="client", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="client", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    scheduling_proposals = relationship("SchedulingProposal", back_populates="client", cascade="all, delete-orphan")


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
    contract_type = Column(String(100), nullable=True)  # one-time, recurring, maintenance
    # Status workflow: new → signed → scheduled → active → completed/cancelled
    # new: Initial lead submission
    # signed: Contract reviewed and signed by both parties
    # scheduled: Client confirmed the schedule slot
    # active: First schedule date has arrived, service in progress
    # cancelled: Owner cancelled the contract
    # completed: Contract term finished
    status = Column(String(50), default="new")
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
    custom_quote = Column(JSON, nullable=True)  # Provider's custom pricing if different from auto-quote
    custom_scope = Column(JSON, nullable=True)  # Provider's custom scope (inclusions/exclusions)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="contracts")
    client = relationship("Client", back_populates="contracts")


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
    calendly_booking_method = Column(String(50), nullable=True)  # 'client_selected', 'provider_created', 'synced'
    
    # Google Calendar integration fields
    google_calendar_event_id = Column(String(500), nullable=True, index=True)  # Google Calendar event ID
    location = Column(String(500), nullable=True)  # Event location (separate from address)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="schedules")
    client = relationship("Client", back_populates="schedules")


class CalendlyIntegration(Base):
    __tablename__ = "calendly_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # OAuth tokens
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)
    
    # Calendly user info
    calendly_user_uri = Column(String(500), nullable=False)
    calendly_user_email = Column(String(255), nullable=True)
    calendly_organization_uri = Column(String(500), nullable=True)
    
    # Selected event type for appointments
    default_event_type_uri = Column(String(500), nullable=True)
    default_event_type_name = Column(String(255), nullable=True)
    default_event_type_url = Column(String(500), nullable=True)
    
    # Settings
    auto_sync_enabled = Column(Boolean, default=True)
    webhook_uuid = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="calendly_integration")


class GoogleCalendarIntegration(Base):
    __tablename__ = "google_calendar_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # OAuth tokens
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)
    
    # Google user info
    google_user_email = Column(String(255), nullable=True)
    google_calendar_id = Column(String(500), nullable=True)  # Primary calendar ID
    
    # Settings
    auto_sync_enabled = Column(Boolean, default=True)
    default_appointment_duration = Column(Integer, default=60)  # Minutes
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="google_calendar_integration")


class SchedulingProposal(Base):
    __tablename__ = "scheduling_proposals"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, accepted, rejected, countered, expired
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


class WaitlistLead(Base):
    __tablename__ = "waitlist_leads"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    business_name = Column(String(255), nullable=True)
    clients_per_month = Column(String(50), nullable=True)  # e.g., "1-5", "6-10", "11-20", "21-50", "50+"
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    source = Column(String(100), default="coming-soon")  # Track where the lead came from
    created_at = Column(DateTime, server_default=func.now())


class IntegrationRequest(Base):
    __tablename__ = "integration_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who submitted the request
    name = Column(String(255), nullable=False)  # Integration name (e.g., "QuickBooks")
    logo_url = Column(String(2000), nullable=False)  # URL or R2 key for the logo (increased for long URLs)
    integration_type = Column(String(100), nullable=False)  # accounting, crm, payment, scheduling, etc.
    use_case = Column(Text, nullable=False)  # Description of how it would be used
    upvotes = Column(Integer, default=1)  # Start with 1 (submitter's implicit vote)
    status = Column(String(50), default="pending")  # pending, approved, in_progress, completed, rejected
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
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
