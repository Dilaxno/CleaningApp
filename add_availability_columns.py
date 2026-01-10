"""
Migration script to add day_schedules, off_work_periods, and custom_addons columns to business_configs table.
Run this script to update the database schema.
"""
import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

# Try to load from backend/.env first, then root .env
backend_env = Path(__file__).parent / ".env"
root_env = Path(__file__).parent.parent / ".env"

if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)

from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable not set")
    print("   Make sure you have a .env file with DATABASE_URL defined")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def add_columns():
    """Add new JSON columns for availability and custom addons"""
    
    columns_to_add = [
        ("day_schedules", "JSON"),
        ("off_work_periods", "JSON"),
        ("custom_addons", "JSON"),
        ("supplies_provided", "VARCHAR(20)"),
        ("available_supplies", "JSON"),
    ]
    
    with engine.connect() as conn:
        for column_name, column_type in columns_to_add:
            try:
                # Check if column exists
                result = conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'business_configs' 
                    AND column_name = '{column_name}'
                """))
                
                if result.fetchone():
                    print(f"✅ Column '{column_name}' already exists")
                else:
                    # Add the column
                    conn.execute(text(f"""
                        ALTER TABLE business_configs 
                        ADD COLUMN {column_name} {column_type}
                    """))
                    conn.commit()
                    print(f"✅ Added column '{column_name}' to business_configs")
                    
            except Exception as e:
                print(f"❌ Error adding column '{column_name}': {e}")
                conn.rollback()

if __name__ == "__main__":
    print("🚀 Adding availability columns to business_configs table...")
    add_columns()
    print("✅ Migration complete!")
