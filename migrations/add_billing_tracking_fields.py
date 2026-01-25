"""
Add billing tracking fields to users table

Migration to add:
- billing_cycle (monthly/yearly)
- last_payment_date
- next_billing_date
- subscription_status

Run with: python migrations/add_billing_tracking_fields.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine

def upgrade():
    """Add billing tracking fields"""
    with engine.connect() as conn:
        # Check if columns already exist to make migration idempotent
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('billing_cycle', 'last_payment_date', 'next_billing_date', 'subscription_status')
        """))
        existing_columns = {row[0] for row in result}
        
        # Add billing_cycle if not exists
        if 'billing_cycle' not in existing_columns:
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN billing_cycle VARCHAR(20)
            """))
            print("✅ Added billing_cycle column")
        else:
            print("ℹ️  billing_cycle column already exists")
        
        # Add last_payment_date if not exists
        if 'last_payment_date' not in existing_columns:
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN last_payment_date TIMESTAMP
            """))
            print("✅ Added last_payment_date column")
        else:
            print("ℹ️  last_payment_date column already exists")
        
        # Add next_billing_date if not exists
        if 'next_billing_date' not in existing_columns:
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN next_billing_date TIMESTAMP
            """))
            print("✅ Added next_billing_date column")
        else:
            print("ℹ️  next_billing_date column already exists")
        
        # Add subscription_status if not exists
        if 'subscription_status' not in existing_columns:
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN subscription_status VARCHAR(50) DEFAULT 'active'
            """))
            print("✅ Added subscription_status column")
        else:
            print("ℹ️  subscription_status column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")

def downgrade():
    """Remove billing tracking fields"""
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_cycle"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS last_payment_date"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS next_billing_date"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS subscription_status"))
        conn.commit()
        print("✅ Migration rolled back successfully!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Manage billing tracking fields migration')
    parser.add_argument('--down', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.down:
        print("Rolling back migration...")
        downgrade()
    else:
        print("Running migration...")
        upgrade()
