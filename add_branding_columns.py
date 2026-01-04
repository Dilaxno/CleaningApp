"""
Migration script to add branding columns to business_configs table.
Run this once to update the database schema.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Add branding columns if they don't exist
        columns_to_add = [
            ("business_name", "VARCHAR(255)"),
            ("logo_url", "VARCHAR(500)"),
            ("signature_url", "VARCHAR(500)"),
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                conn.execute(text(f"""
                    ALTER TABLE business_configs 
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                """))
                print(f"✅ Added column: {column_name}")
            except Exception as e:
                print(f"⚠️ Column {column_name} might already exist: {e}")
        
        conn.commit()
        print("✅ Migration completed!")

if __name__ == "__main__":
    migrate()
