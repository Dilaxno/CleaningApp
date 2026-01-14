"""
Migration script to add payout information columns to users table.
Run this script to add the columns needed for storing user payout/bank details.
"""
import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable not set")
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)

# SQL to add payout columns
ADD_COLUMNS_SQL = """
-- Add payout information columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_country VARCHAR(2);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_currency VARCHAR(3);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_account_holder_name VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_bank_name VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_account_number VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_routing_number VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_iban VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_swift_bic VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_bank_address VARCHAR(500);
"""

def run_migration():
    print("🚀 Starting payout columns migration...")
    
    with engine.connect() as conn:
        # Execute each statement separately
        statements = [s.strip() for s in ADD_COLUMNS_SQL.strip().split(';') if s.strip() and not s.strip().startswith('--')]
        
        for statement in statements:
            try:
                print(f"  Executing: {statement[:60]}...")
                conn.execute(text(statement))
                conn.commit()
                print("  ✅ Success")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  ⚠️ Column already exists, skipping")
                else:
                    print(f"  ❌ Error: {e}")
    
    print("\n✅ Migration completed!")

if __name__ == "__main__":
    run_migration()
