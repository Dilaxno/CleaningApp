"""
Migration script to create waitlist_leads table
Run this once to create the table in Neon DB
"""
import os
import sys
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

def create_waitlist_leads_table():
    """Create the waitlist_leads table"""
    engine = create_engine(DATABASE_URL)
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS waitlist_leads (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        business_name VARCHAR(255),
        clients_per_month VARCHAR(50),
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        source VARCHAR(100) DEFAULT 'coming-soon',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_waitlist_leads_email ON waitlist_leads(email);
    CREATE INDEX IF NOT EXISTS idx_waitlist_leads_created_at ON waitlist_leads(created_at);
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✅ waitlist_leads table created successfully!")

if __name__ == "__main__":
    create_waitlist_leads_table()
