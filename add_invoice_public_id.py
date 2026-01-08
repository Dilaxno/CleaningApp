"""
Migration script to add public_id column to invoices table.
Run this script to add UUID-based public access to invoices.

Usage: python add_invoice_public_id.py
"""
import uuid
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text
from app.config import DATABASE_URL

def migrate():
    """Add public_id column to invoices table and populate existing rows"""
    if not DATABASE_URL:
        print("❌ DATABASE_URL not configured")
        return False
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'invoices' AND column_name = 'public_id'
        """))
        
        if result.fetchone():
            print("✅ public_id column already exists")
        else:
            # Add the column
            print("📝 Adding public_id column to invoices table...")
            conn.execute(text("""
                ALTER TABLE invoices 
                ADD COLUMN public_id VARCHAR(36) UNIQUE
            """))
            conn.commit()
            print("✅ Column added")
        
        # Populate existing rows with UUIDs
        print("📝 Populating existing invoices with UUIDs...")
        result = conn.execute(text("SELECT id FROM invoices WHERE public_id IS NULL"))
        rows = result.fetchall()
        
        for row in rows:
            new_uuid = str(uuid.uuid4())
            conn.execute(
                text("UPDATE invoices SET public_id = :uuid WHERE id = :id"),
                {"uuid": new_uuid, "id": row[0]}
            )
        
        conn.commit()
        print(f"✅ Updated {len(rows)} invoices with UUIDs")
        
        # Make column NOT NULL after populating
        print("📝 Making public_id column NOT NULL...")
        conn.execute(text("""
            ALTER TABLE invoices 
            ALTER COLUMN public_id SET NOT NULL
        """))
        conn.commit()
        print("✅ Column is now NOT NULL")
        
        # Add index if not exists
        print("📝 Adding index on public_id...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_invoices_public_id ON invoices(public_id)
        """))
        conn.commit()
        print("✅ Index created")
    
    print("\n🎉 Migration complete!")
    return True

if __name__ == "__main__":
    migrate()
