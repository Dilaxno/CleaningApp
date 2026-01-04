"""
Add form_data column to clients table
"""
import os
import sys
from sqlalchemy import create_engine, text

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

def add_form_data_column():
    """Add form_data JSON column to clients table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Adding form_data column to clients table...")
        
        try:
            # Add form_data column as JSON type
            conn.execute(text("""
                ALTER TABLE clients 
                ADD COLUMN IF NOT EXISTS form_data JSONB
            """))
            conn.commit()
            print("✅ Successfully added form_data column to clients table")
            
        except Exception as e:
            print(f"❌ Error adding form_data column: {e}")
            conn.rollback()
            raise
    
    print("Migration complete!")

if __name__ == "__main__":
    add_form_data_column()
