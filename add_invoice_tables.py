"""
Migration script to add Invoice and Payout tables
Run: python add_invoice_tables.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config import DATABASE_URL

def run_migration():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        return
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Create invoices table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                client_id INTEGER NOT NULL REFERENCES clients(id),
                contract_id INTEGER REFERENCES contracts(id),
                schedule_id INTEGER REFERENCES schedules(id),
                invoice_number VARCHAR(50) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                service_type VARCHAR(100),
                base_amount FLOAT NOT NULL,
                frequency_discount FLOAT DEFAULT 0,
                addon_amount FLOAT DEFAULT 0,
                tax_amount FLOAT DEFAULT 0,
                total_amount FLOAT NOT NULL,
                currency VARCHAR(10) DEFAULT 'USD',
                is_recurring BOOLEAN DEFAULT FALSE,
                recurrence_pattern VARCHAR(50),
                billing_interval VARCHAR(20),
                billing_interval_count INTEGER DEFAULT 1,
                status VARCHAR(50) DEFAULT 'pending',
                dodo_product_id VARCHAR(255),
                dodo_payment_link VARCHAR(500),
                dodo_payment_id VARCHAR(255),
                pdf_key VARCHAR(500),
                issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date TIMESTAMP,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Created invoices table")
        
        # Create index on invoice_number
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number ON invoices(invoice_number)
        """))
        print("✅ Created index on invoice_number")
        
        # Create payouts table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payouts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount FLOAT NOT NULL,
                currency VARCHAR(10) DEFAULT 'USD',
                status VARCHAR(50) DEFAULT 'pending',
                invoice_ids JSONB DEFAULT '[]',
                payout_method VARCHAR(50),
                payout_details JSONB,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                completed_at TIMESTAMP,
                reference_id VARCHAR(255),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Created payouts table")
        
        conn.commit()
        print("✅ Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
