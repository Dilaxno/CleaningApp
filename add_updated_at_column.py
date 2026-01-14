"""
Migration script to add updated_at column to users table.
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

def run_migration():
    print("🚀 Adding updated_at column to users table...")
    
    with engine.connect() as conn:
        try:
            # Add updated_at column with default value
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            conn.commit()
            print("✅ updated_at column added successfully!")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("⚠️ Column already exists, skipping")
            else:
                print(f"❌ Error: {e}")
                raise

if __name__ == "__main__":
    run_migration()
