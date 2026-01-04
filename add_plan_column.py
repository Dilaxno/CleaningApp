"""
Migration script to add plan column to users table.
Run this script once to add the plan column with default value 'free'.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def add_plan_column():
    """Add plan column to users table with default value 'free'"""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'plan'
        """))
        
        if result.fetchone():
            print("✅ Column 'plan' already exists in users table")
            return
        
        # Add the column
        print("📝 Adding 'plan' column to users table...")
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN plan VARCHAR(50) DEFAULT 'free' NOT NULL
        """))
        conn.commit()
        print("✅ Column 'plan' added successfully with default value 'free'")
        
        # Update existing users to have 'free' plan
        result = conn.execute(text("UPDATE users SET plan = 'free' WHERE plan IS NULL"))
        conn.commit()
        print(f"✅ Updated {result.rowcount} existing users to 'free' plan")

if __name__ == "__main__":
    add_plan_column()
