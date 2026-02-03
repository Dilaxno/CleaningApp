"""
Add billing address columns to users table

Columns:
- billing_street VARCHAR(500)
- billing_city VARCHAR(255)
- billing_state VARCHAR(255)
- billing_zipcode VARCHAR(20)
- billing_country VARCHAR(2)
- billing_updated_at TIMESTAMP
"""

# Ensure this script can be run directly from repo root or backend folder
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent  # backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.database import engine


def upgrade():
    with engine.connect() as conn:
        # Add columns to users table (idempotent)
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_street VARCHAR(500);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_city VARCHAR(255);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_state VARCHAR(255);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_zipcode VARCHAR(20);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_country VARCHAR(2);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS billing_updated_at TIMESTAMP;
                """
            )
        )
        conn.commit()
        print("Migration add_billing_address_fields applied successfully")


def downgrade():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_updated_at"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_country"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_zipcode"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_state"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_city"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS billing_street"))
        conn.commit()
        print("Migration add_billing_address_fields rolled back")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage billing address fields migration")
    parser.add_argument("--down", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    if args.down:
        downgrade()
    else:
        upgrade()