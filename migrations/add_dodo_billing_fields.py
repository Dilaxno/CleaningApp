"""
Add Dodo Payments linkage fields and subscription payments table

- Users table: store NON-PCI metadata only for default payment method
  * dodo_customer_id
  * dodo_default_payment_method_id
  * dodo_payment_method_brand
  * dodo_payment_method_last4
  * dodo_payment_method_exp_month (INTEGER)
  * dodo_payment_method_exp_year (INTEGER)
  * dodo_payment_method_type

- subscription_payments table: track platform subscription charges to providers
"""

# Ensure this script can be run directly from repo root or backend folder
import sys
from pathlib import Path

# Add backend/ to sys.path so "app" package is importable
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
                ADD COLUMN IF NOT EXISTS dodo_customer_id VARCHAR(255);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_default_payment_method_id VARCHAR(255);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_payment_method_brand VARCHAR(50);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_payment_method_last4 VARCHAR(4);
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_payment_method_exp_month INTEGER;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_payment_method_exp_year INTEGER;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS dodo_payment_method_type VARCHAR(50);
                """
            )
        )

        # Create subscription_payments table if not exists
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS subscription_payments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    dodo_payment_id VARCHAR(255) UNIQUE NOT NULL,
                    dodo_subscription_id VARCHAR(255),
                    dodo_customer_id VARCHAR(255),
                    amount DOUBLE PRECISION,
                    amount_lowest_unit INTEGER,
                    currency VARCHAR(10) DEFAULT 'USD',
                    status VARCHAR(50) DEFAULT 'paid',
                    description TEXT,
                    invoice_number VARCHAR(100),
                    paid_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
        )

        conn.commit()
        print("Migration add_dodo_billing_fields applied successfully")


def downgrade():
    with engine.connect() as conn:
        # Drop subscription_payments table
        conn.execute(text("DROP TABLE IF EXISTS subscription_payments"))
        # Drop user columns
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_payment_method_type"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_payment_method_exp_year"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_payment_method_exp_month"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_payment_method_last4"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_payment_method_brand"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_default_payment_method_id"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS dodo_customer_id"))
        conn.commit()
        print("Migration add_dodo_billing_fields rolled back")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Dodo billing linkage migration")
    parser.add_argument("--down", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    if args.down:
        downgrade()
    else:
        upgrade()