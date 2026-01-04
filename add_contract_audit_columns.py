"""
Migration script to add signature audit trail and legal columns to contracts table
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

def migrate():
    columns_to_add = [
        ("currency", "VARCHAR(10) DEFAULT 'USD'"),
        ("pdf_hash", "VARCHAR(64)"),
        ("signature_ip", "VARCHAR(45)"),
        ("signature_user_agent", "VARCHAR(500)"),
        ("signature_timestamp", "TIMESTAMP"),
        ("jurisdiction", "VARCHAR(255)"),
    ]
    
    with engine.connect() as conn:
        for column_name, column_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE contracts ADD COLUMN {column_name} {column_type}"))
                conn.commit()
                print(f"✅ Added {column_name} column to contracts table")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"ℹ️  Column {column_name} already exists")
                else:
                    print(f"⚠️  Error adding {column_name}: {e}")

if __name__ == "__main__":
    migrate()
