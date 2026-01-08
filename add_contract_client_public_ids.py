"""
Migration script to add public_id columns to contracts and clients tables.
Run this script to add UUID-based public access to contracts and clients.

Usage: python add_contract_client_public_ids.py
"""
import uuid
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text
from app.config import DATABASE_URL


def add_public_id_column(conn, table_name: str):
    """Add public_id column to a table and populate existing rows"""
    # Check if column already exists
    result = conn.execute(text(f"""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = '{table_name}' AND column_name = 'public_id'
    """))
    
    if result.fetchone():
        print(f"✅ public_id column already exists in {table_name}")
    else:
        print(f"📝 Adding public_id column to {table_name} table...")
        conn.execute(text(f"""
            ALTER TABLE {table_name} 
            ADD COLUMN public_id VARCHAR(36) UNIQUE
        """))
        conn.commit()
        print(f"✅ Column added to {table_name}")
    
    # Populate existing rows with UUIDs
    print(f"📝 Populating existing {table_name} with UUIDs...")
    result = conn.execute(text(f"SELECT id FROM {table_name} WHERE public_id IS NULL"))
    rows = result.fetchall()
    
    for row in rows:
        new_uuid = str(uuid.uuid4())
        conn.execute(
            text(f"UPDATE {table_name} SET public_id = :uuid WHERE id = :id"),
            {"uuid": new_uuid, "id": row[0]}
        )
    
    conn.commit()
    print(f"✅ Updated {len(rows)} {table_name} with UUIDs")
    
    # Make column NOT NULL after populating
    if rows:
        print(f"📝 Making public_id column NOT NULL in {table_name}...")
        conn.execute(text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN public_id SET NOT NULL
        """))
        conn.commit()
        print(f"✅ Column is now NOT NULL in {table_name}")
    
    # Add index if not exists
    print(f"📝 Adding index on public_id for {table_name}...")
    conn.execute(text(f"""
        CREATE INDEX IF NOT EXISTS ix_{table_name}_public_id ON {table_name}(public_id)
    """))
    conn.commit()
    print(f"✅ Index created for {table_name}")


def migrate():
    """Add public_id columns to contracts and clients tables"""
    if not DATABASE_URL:
        print("❌ DATABASE_URL not configured")
        return False
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Add to clients table
        print("\n=== Processing clients table ===")
        add_public_id_column(conn, "clients")
        
        # Add to contracts table
        print("\n=== Processing contracts table ===")
        add_public_id_column(conn, "contracts")
    
    print("\n🎉 Migration complete!")
    return True


if __name__ == "__main__":
    migrate()
