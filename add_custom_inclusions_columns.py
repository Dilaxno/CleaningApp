"""
Migration script to add custom_inclusions and custom_exclusions columns to business_configs table.
Run this script to add the new columns for custom service inclusions/exclusions.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def add_columns():
    """Add custom_inclusions and custom_exclusions columns to business_configs table."""
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'business_configs' 
            AND column_name IN ('custom_inclusions', 'custom_exclusions')
        """))
        existing_columns = [row[0] for row in result.fetchall()]
        
        if 'custom_inclusions' not in existing_columns:
            print("Adding custom_inclusions column...")
            conn.execute(text("""
                ALTER TABLE business_configs 
                ADD COLUMN custom_inclusions JSON DEFAULT '[]'
            """))
            print("✅ custom_inclusions column added")
        else:
            print("ℹ️ custom_inclusions column already exists")
        
        if 'custom_exclusions' not in existing_columns:
            print("Adding custom_exclusions column...")
            conn.execute(text("""
                ALTER TABLE business_configs 
                ADD COLUMN custom_exclusions JSON DEFAULT '[]'
            """))
            print("✅ custom_exclusions column added")
        else:
            print("ℹ️ custom_exclusions column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    add_columns()
