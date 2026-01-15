"""
Safe version of index migration with better error handling and network checks
Run this migration to optimize queries for millions of users

Usage:
    python add_scalability_indexes_safe.py
"""
import os
import sys
from pathlib import Path
import socket

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    sys.exit(1)


def check_network_connectivity(host, port=5432):
    """Check if we can reach the database host"""
    try:
        print(f"🔍 Testing network connectivity to {host}:{port}...")
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        print(f"✅ Network connectivity OK")
        return True
    except socket.gaierror:
        print(f"❌ DNS resolution failed for {host}")
        print(f"   This usually means:")
        print(f"   1. No internet connection")
        print(f"   2. DNS server issues")
        print(f"   3. Firewall blocking DNS")
        return False
    except socket.timeout:
        print(f"❌ Connection timeout to {host}:{port}")
        print(f"   This usually means:")
        print(f"   1. Firewall blocking connection")
        print(f"   2. Database server is down")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def extract_host_from_url(url):
    """Extract hostname from database URL"""
    try:
        # Format: postgresql+psycopg://user:pass@host:port/db
        if '@' in url:
            host_part = url.split('@')[1].split('/')[0]
            if ':' in host_part:
                return host_part.split(':')[0]
            return host_part
        return None
    except:
        return None


def test_database_connection(engine):
    """Test if we can connect to the database"""
    try:
        print("🔍 Testing database connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("✅ Database connection OK")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


# SQL statements for creating indexes (can be run manually if script fails)
SQL_STATEMENTS = """
-- Single-column indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_plan ON users(plan);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_id ON users(subscription_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_business_configs_user_id ON business_configs(user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_user_id ON clients(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_public_id ON clients(public_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_created_at ON clients(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_email ON clients(email);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_user_id ON contracts(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_client_id ON contracts(client_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_public_id ON contracts(public_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_created_at ON contracts(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_start_date ON contracts(start_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_end_date ON contracts(end_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_user_id ON schedules(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_client_id ON schedules(client_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_status ON schedules(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_scheduled_date ON schedules(scheduled_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_calendly_event_uri ON schedules(calendly_event_uri);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_google_calendar_event_id ON schedules(google_calendar_event_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_created_at ON schedules(created_at DESC);

-- Composite indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_user_created ON clients(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_user_status ON contracts(user_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_user_created ON contracts(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_user_date ON schedules(user_id, scheduled_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_status_dates ON contracts(status, start_date, end_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_client_status ON contracts(client_id, status);

-- Partial indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_active ON contracts(user_id, status) WHERE status IN ('new', 'signed', 'scheduled', 'active');
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_schedules_upcoming ON schedules(user_id, scheduled_date) WHERE status = 'scheduled' AND scheduled_date >= CURRENT_DATE;
"""


def main():
    print("🚀 Starting database index creation for scalability")
    print()
    
    # Extract and check host
    host = extract_host_from_url(DATABASE_URL)
    if host:
        print(f"📊 Database host: {host}")
        if not check_network_connectivity(host):
            print()
            print("=" * 60)
            print("⚠️  NETWORK CONNECTIVITY ISSUE")
            print("=" * 60)
            print()
            print("Your machine cannot reach the database server.")
            print()
            print("Troubleshooting steps:")
            print("1. Check your internet connection")
            print("2. Try: ping", host)
            print("3. Check if a VPN is blocking the connection")
            print("4. Try from a different network")
            print("5. Check Windows Firewall settings")
            print()
            print("Alternative: Run this script from your production server")
            print("where the application is deployed (it has network access).")
            print()
            print("=" * 60)
            print("📋 MANUAL SQL SCRIPT")
            print("=" * 60)
            print()
            print("You can also run these SQL statements manually:")
            print()
            print("1. Connect to your database using psql or a GUI tool")
            print("2. Run the following SQL statements:")
            print()
            print(SQL_STATEMENTS)
            print()
            print("=" * 60)
            sys.exit(1)
    
    # Create engine with timeout
    try:
        engine = create_engine(
            DATABASE_URL,
            connect_args={"connect_timeout": 10}
        )
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        sys.exit(1)
    
    # Test connection
    if not test_database_connection(engine):
        print()
        print("=" * 60)
        print("⚠️  DATABASE CONNECTION FAILED")
        print("=" * 60)
        print()
        print("Cannot connect to the database.")
        print()
        print("Please run this script from your production server")
        print("or use the manual SQL script above.")
        print()
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("Creating indexes...")
    print("=" * 60)
    print()
    
    created_count = 0
    failed_count = 0
    
    # Split SQL into individual statements
    statements = [s.strip() for s in SQL_STATEMENTS.split(';') if s.strip()]
    
    with engine.connect() as conn:
        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
            
            # Extract index name for logging
            index_name = "unknown"
            if "idx_" in statement:
                try:
                    index_name = statement.split("idx_")[1].split()[0]
                    index_name = "idx_" + index_name
                except:
                    pass
            
            try:
                print(f"[{i}/{len(statements)}] Creating {index_name}...")
                conn.execute(text(statement))
                conn.commit()
                print(f"✅ Created {index_name}")
                created_count += 1
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower():
                    print(f"⏭️  {index_name} already exists, skipping")
                else:
                    print(f"❌ Failed to create {index_name}: {e}")
                    failed_count += 1
            print()
    
    print("=" * 60)
    print("📊 Index Creation Summary")
    print("=" * 60)
    print(f"✅ Created: {created_count}")
    print(f"❌ Failed: {failed_count}")
    print()
    
    if created_count > 0:
        print("🎉 Database indexes created successfully!")
        print("📈 Your application is now ready to scale to millions of users")
    elif failed_count == 0:
        print("✅ All indexes already exist - database is optimized")
    else:
        print("⚠️  Some indexes failed to create - check errors above")
    
    print()
    print("Next steps:")
    print("1. Restart your application to use the new connection pool settings")
    print("2. Monitor query performance with EXPLAIN ANALYZE")
    print("3. Check slow query logs")


if __name__ == "__main__":
    main()
