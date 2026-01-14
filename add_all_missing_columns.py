"""
Migration script to add all missing columns to users table.
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

COLUMNS_TO_ADD = [
    ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("payout_country", "VARCHAR(2)"),
    ("payout_currency", "VARCHAR(3)"),
    ("payout_account_holder_name", "VARCHAR(255)"),
    ("payout_bank_name", "VARCHAR(255)"),
    ("payout_account_number", "VARCHAR(50)"),
    ("payout_routing_number", "VARCHAR(50)"),
    ("payout_iban", "VARCHAR(50)"),
    ("payout_swift_bic", "VARCHAR(20)"),
    ("payout_bank_address", "VARCHAR(500)"),
]

def run_migration():
    print("🚀 Adding missing columns to users table...")
    
    with engine.connect() as conn:
        for col_name, col_type in COLUMNS_TO_ADD:
            try:
                sql = f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                print(f"  Adding {col_name}...")
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✅ {col_name} added")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  ⚠️ {col_name} already exists")
                else:
                    print(f"  ❌ Error adding {col_name}: {e}")
    
    print("\n✅ Migration completed!")

if __name__ == "__main__":
    run_migration()
