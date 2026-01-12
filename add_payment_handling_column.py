"""
Migration script to add payment_handling column to business_configs table
Run this script to add the new column for payment handling preference
"""
import os
import sys

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

def add_payment_handling_column():
    """Add payment_handling column to business_configs table"""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'business_configs' AND column_name = 'payment_handling'
        """))
        
        if result.fetchone():
            print("✅ Column 'payment_handling' already exists in business_configs table")
            return
        
        # Add the column
        conn.execute(text("""
            ALTER TABLE business_configs 
            ADD COLUMN payment_handling VARCHAR(20)
        """))
        conn.commit()
        print("✅ Successfully added 'payment_handling' column to business_configs table")

if __name__ == "__main__":
    add_payment_handling_column()
