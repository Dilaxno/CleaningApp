"""
Migration script to add subscription_id column to users table.
Run this script once to add the column used for Dodo Payments subscription linkage.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)


def add_subscription_id_column():
    """Add subscription_id column to users table if it does not exist"""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            text(
                """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'subscription_id'
        """
            )
        )

        if result.fetchone():
            print("✅ Column 'subscription_id' already exists in users table")
            return

        # Add the column
        print("📝 Adding 'subscription_id' column to users table...")
        conn.execute(
            text(
                """
            ALTER TABLE users 
            ADD COLUMN subscription_id VARCHAR(255) NULL
        """
            )
        )
        conn.commit()
        print("✅ Column 'subscription_id' added successfully")


if __name__ == "__main__":
    add_subscription_id_column()