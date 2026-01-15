"""
Add comprehensive database indexes for scalability
Run this migration to optimize queries for millions of users

Usage:
    python add_scalability_indexes.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# Define all indexes to create
INDEXES = [
    # Users table
    ("idx_users_firebase_uid", "users", "firebase_uid"),
    ("idx_users_email", "users", "email"),
    ("idx_users_plan", "users", "plan"),
    ("idx_users_subscription_id", "users", "subscription_id"),
    
    # Business configs table
    ("idx_business_configs_user_id", "business_configs", "user_id"),
    
    # Clients table
    ("idx_clients_user_id", "clients", "user_id"),
    ("idx_clients_public_id", "clients", "public_id"),
    ("idx_clients_status", "clients", "status"),
    ("idx_clients_created_at", "clients", "created_at DESC"),
    ("idx_clients_email", "clients", "email"),
    
    # Contracts table
    ("idx_contracts_user_id", "contracts", "user_id"),
    ("idx_contracts_client_id", "contracts", "client_id"),
    ("idx_contracts_public_id", "contracts", "public_id"),
    ("idx_contracts_status", "contracts", "status"),
    ("idx_contracts_created_at", "contracts", "created_at DESC"),
    ("idx_contracts_start_date", "contracts", "start_date"),
    ("idx_contracts_end_date", "contracts", "end_date"),
    
    # Schedules table
    ("idx_schedules_user_id", "schedules", "user_id"),
    ("idx_schedules_client_id", "schedules", "client_id"),
    ("idx_schedules_status", "schedules", "status"),
    ("idx_schedules_scheduled_date", "schedules", "scheduled_date"),
    ("idx_schedules_calendly_event_uri", "schedules", "calendly_event_uri"),
    ("idx_schedules_google_calendar_event_id", "schedules", "google_calendar_event_id"),
    ("idx_schedules_created_at", "schedules", "created_at DESC"),
    
    # Invoices table (if exists)
    ("idx_invoices_user_id", "invoices", "user_id"),
    ("idx_invoices_client_id", "invoices", "client_id"),
    ("idx_invoices_contract_id", "invoices", "contract_id"),
    ("idx_invoices_public_id", "invoices", "public_id"),
    ("idx_invoices_status", "invoices", "status"),
    ("idx_invoices_due_date", "invoices", "due_date"),
    
    # Calendly integrations table
    ("idx_calendly_integrations_user_id", "calendly_integrations", "user_id"),
    
    # Google Calendar integrations table
    ("idx_google_calendar_integrations_user_id", "google_calendar_integrations", "user_id"),
    
    # Scheduling proposals table
    ("idx_scheduling_proposals_contract_id", "scheduling_proposals", "contract_id"),
    ("idx_scheduling_proposals_client_id", "scheduling_proposals", "client_id"),
    ("idx_scheduling_proposals_user_id", "scheduling_proposals", "user_id"),
    ("idx_scheduling_proposals_status", "scheduling_proposals", "status"),
    
    # Waitlist leads table
    ("idx_waitlist_leads_email", "waitlist_leads", "email"),
    ("idx_waitlist_leads_created_at", "waitlist_leads", "created_at DESC"),
    
    # Integration requests table
    ("idx_integration_requests_user_id", "integration_requests", "user_id"),
    ("idx_integration_requests_status", "integration_requests", "status"),
    
    # Integration request votes table
    ("idx_integration_request_votes_request_id", "integration_request_votes", "integration_request_id"),
    ("idx_integration_request_votes_user_id", "integration_request_votes", "user_id"),
]

# Composite indexes for common query patterns
COMPOSITE_INDEXES = [
    # User's clients ordered by creation date
    ("idx_clients_user_created", "clients", ["user_id", "created_at DESC"]),
    
    # User's contracts by status
    ("idx_contracts_user_status", "contracts", ["user_id", "status"]),
    
    # User's contracts ordered by creation date
    ("idx_contracts_user_created", "contracts", ["user_id", "created_at DESC"]),
    
    # User's schedules by date
    ("idx_schedules_user_date", "schedules", ["user_id", "scheduled_date"]),
    
    # Active contracts for status automation
    ("idx_contracts_status_dates", "contracts", ["status", "start_date", "end_date"]),
    
    # Client's contracts by status
    ("idx_contracts_client_status", "contracts", ["client_id", "status"]),
]

# Partial indexes for specific queries (PostgreSQL only)
PARTIAL_INDEXES = [
    # Only index active/pending contracts (reduces index size)
    (
        "idx_contracts_active",
        "contracts",
        ["user_id", "status"],
        "status IN ('new', 'signed', 'scheduled', 'active')"
    ),
    
    # Only index upcoming schedules
    (
        "idx_schedules_upcoming",
        "schedules",
        ["user_id", "scheduled_date"],
        "status = 'scheduled' AND scheduled_date >= CURRENT_DATE"
    ),
    
    # Only index pending scheduling proposals
    (
        "idx_scheduling_proposals_pending",
        "scheduling_proposals",
        ["user_id", "status"],
        "status = 'pending'"
    ),
]


def index_exists(conn, index_name):
    """Check if an index already exists"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE indexname = :index_name
        )
    """), {"index_name": index_name})
    return result.scalar()


def table_exists(conn, table_name):
    """Check if a table exists"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = :table_name
        )
    """), {"table_name": table_name})
    return result.scalar()


def create_index(conn, index_name, table_name, column):
    """Create a single-column index"""
    if index_exists(conn, index_name):
        print(f"⏭️  Index {index_name} already exists, skipping")
        return False
    
    if not table_exists(conn, table_name):
        print(f"⚠️  Table {table_name} does not exist, skipping index {index_name}")
        return False
    
    try:
        sql = f"CREATE INDEX CONCURRENTLY {index_name} ON {table_name} ({column})"
        print(f"📊 Creating index: {index_name} on {table_name}({column})")
        conn.execute(text(sql))
        conn.commit()
        print(f"✅ Created index: {index_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create index {index_name}: {e}")
        conn.rollback()
        return False


def create_composite_index(conn, index_name, table_name, columns):
    """Create a composite index"""
    if index_exists(conn, index_name):
        print(f"⏭️  Index {index_name} already exists, skipping")
        return False
    
    if not table_exists(conn, table_name):
        print(f"⚠️  Table {table_name} does not exist, skipping index {index_name}")
        return False
    
    try:
        columns_str = ", ".join(columns)
        sql = f"CREATE INDEX CONCURRENTLY {index_name} ON {table_name} ({columns_str})"
        print(f"📊 Creating composite index: {index_name} on {table_name}({columns_str})")
        conn.execute(text(sql))
        conn.commit()
        print(f"✅ Created composite index: {index_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create composite index {index_name}: {e}")
        conn.rollback()
        return False


def create_partial_index(conn, index_name, table_name, columns, where_clause):
    """Create a partial index with WHERE clause"""
    if index_exists(conn, index_name):
        print(f"⏭️  Index {index_name} already exists, skipping")
        return False
    
    if not table_exists(conn, table_name):
        print(f"⚠️  Table {table_name} does not exist, skipping index {index_name}")
        return False
    
    try:
        columns_str = ", ".join(columns)
        sql = f"CREATE INDEX CONCURRENTLY {index_name} ON {table_name} ({columns_str}) WHERE {where_clause}"
        print(f"📊 Creating partial index: {index_name} on {table_name}({columns_str}) WHERE {where_clause}")
        conn.execute(text(sql))
        conn.commit()
        print(f"✅ Created partial index: {index_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create partial index {index_name}: {e}")
        conn.rollback()
        return False


def main():
    print("🚀 Starting database index creation for scalability")
    print(f"📊 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    print()
    
    created_count = 0
    skipped_count = 0
    failed_count = 0
    
    with engine.connect() as conn:
        # Create single-column indexes
        print("=" * 60)
        print("Creating single-column indexes...")
        print("=" * 60)
        for index_name, table_name, column in INDEXES:
            result = create_index(conn, index_name, table_name, column)
            if result:
                created_count += 1
            elif index_exists(conn, index_name):
                skipped_count += 1
            else:
                failed_count += 1
            print()
        
        # Create composite indexes
        print("=" * 60)
        print("Creating composite indexes...")
        print("=" * 60)
        for index_name, table_name, columns in COMPOSITE_INDEXES:
            result = create_composite_index(conn, index_name, table_name, columns)
            if result:
                created_count += 1
            elif index_exists(conn, index_name):
                skipped_count += 1
            else:
                failed_count += 1
            print()
        
        # Create partial indexes
        print("=" * 60)
        print("Creating partial indexes...")
        print("=" * 60)
        for index_name, table_name, columns, where_clause in PARTIAL_INDEXES:
            result = create_partial_index(conn, index_name, table_name, columns, where_clause)
            if result:
                created_count += 1
            elif index_exists(conn, index_name):
                skipped_count += 1
            else:
                failed_count += 1
            print()
    
    print("=" * 60)
    print("📊 Index Creation Summary")
    print("=" * 60)
    print(f"✅ Created: {created_count}")
    print(f"⏭️  Skipped (already exist): {skipped_count}")
    print(f"❌ Failed: {failed_count}")
    print()
    
    if created_count > 0:
        print("🎉 Database indexes created successfully!")
        print("📈 Your application is now ready to scale to millions of users")
    elif skipped_count > 0 and failed_count == 0:
        print("✅ All indexes already exist - database is optimized")
    else:
        print("⚠️  Some indexes failed to create - check errors above")
    
    print()
    print("Next steps:")
    print("1. Monitor query performance with EXPLAIN ANALYZE")
    print("2. Add pagination to list endpoints")
    print("3. Implement caching layer")
    print("4. Scale background workers")


if __name__ == "__main__":
    main()
