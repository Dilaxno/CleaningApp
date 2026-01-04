"""
Migration script to add pdf_key column to contracts table
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def add_pdf_key_column():
    """Add pdf_key column to contracts table"""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'contracts' AND column_name = 'pdf_key'
        """))
        
        if result.fetchone():
            print("✅ pdf_key column already exists")
            return
        
        # Add the column
        conn.execute(text("""
            ALTER TABLE contracts 
            ADD COLUMN pdf_key VARCHAR(500) NULL
        """))
        conn.commit()
        print("✅ Added pdf_key column to contracts table")

if __name__ == "__main__":
    add_pdf_key_column()
