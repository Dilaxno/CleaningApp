"""
Migration script to add client signature columns to contracts table.
Run this script to add the new columns for dual-signature workflow.
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

columns_to_add = [
    ("client_signature", "TEXT"),
    ("client_signature_ip", "VARCHAR(45)"),
    ("client_signature_user_agent", "VARCHAR(500)"),
    ("client_signature_timestamp", "TIMESTAMP"),
]

for column_name, column_type in columns_to_add:
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE contracts ADD COLUMN {column_name} {column_type}"))
            conn.commit()
            print(f"✅ Added column: {column_name}")
    except Exception as e:
        if "Duplicate column" in str(e) or "already exists" in str(e).lower():
            print(f"⏭️  Column already exists: {column_name}")
        else:
            print(f"❌ Error adding {column_name}: {e}")

print("\n✅ Migration complete!")
