#!/usr/bin/env python3
"""
Migration script to add payment notification fields to users table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine, get_db
from app.models import User

def add_payment_notification_fields():
    """Add unread_payments_count and last_payment_check fields to users table"""
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('unread_payments_count', 'last_payment_check')
        """))
        existing_columns = [row[0] for row in result]
        
        if 'unread_payments_count' not in existing_columns:
            print("Adding unread_payments_count column...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN unread_payments_count INTEGER NOT NULL DEFAULT 0
            """))
            conn.commit()
            print("✅ Added unread_payments_count column")
        else:
            print("⚠️ unread_payments_count column already exists")
            
        if 'last_payment_check' not in existing_columns:
            print("Adding last_payment_check column...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN last_payment_check TIMESTAMP NULL
            """))
            conn.commit()
            print("✅ Added last_payment_check column")
        else:
            print("⚠️ last_payment_check column already exists")

if __name__ == "__main__":
    print("🔄 Adding payment notification fields to users table...")
    try:
        add_payment_notification_fields()
        print("✅ Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)