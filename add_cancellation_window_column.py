"""
Migration script to add cancellation_window column to business_configs table.
Run this script to add the column for existing databases.
"""
import os
import sys
from sqlalchemy import create_engine, text

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import DATABASE_URL

def migrate():
    """Add cancellation_window column to business_configs table."""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'business_configs' 
            AND column_name = 'cancellation_window'
        """))
        
        if result.fetchone():
            print("✅ Column 'cancellation_window' already exists in business_configs table")
            return
        
        # Add the column
        print("Adding 'cancellation_window' column to business_configs table...")
        conn.execute(text("""
            ALTER TABLE business_configs 
            ADD COLUMN cancellation_window INTEGER DEFAULT 24
        """))
        conn.commit()
        print("✅ Successfully added 'cancellation_window' column")

if __name__ == "__main__":
    migrate()
