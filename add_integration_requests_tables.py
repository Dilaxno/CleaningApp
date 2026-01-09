"""
Migration script to add integration_requests and integration_request_votes tables
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

def run_migration():
    print("🔄 Adding integration_requests and integration_request_votes tables...")
    
    with engine.connect() as conn:
        # Create integration_requests table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS integration_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                logo_url VARCHAR(2000) NOT NULL,
                integration_type VARCHAR(100) NOT NULL,
                use_case TEXT NOT NULL,
                upvotes INTEGER DEFAULT 1,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Created integration_requests table")
        
        # Alter logo_url column if table already exists with smaller size
        try:
            conn.execute(text("""
                ALTER TABLE integration_requests 
                ALTER COLUMN logo_url TYPE VARCHAR(2000)
            """))
            print("✅ Updated logo_url column size to 2000")
        except Exception as e:
            print(f"ℹ️ logo_url column already correct size or table just created: {e}")
        
        # Create integration_request_votes table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS integration_request_votes (
                id SERIAL PRIMARY KEY,
                integration_request_id INTEGER NOT NULL REFERENCES integration_requests(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(integration_request_id, user_id)
            )
        """))
        print("✅ Created integration_request_votes table")
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_integration_requests_upvotes 
            ON integration_requests(upvotes DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_integration_request_votes_user 
            ON integration_request_votes(user_id)
        """))
        print("✅ Created indexes")
        
        conn.commit()
    
    print("✅ Migration complete!")

if __name__ == "__main__":
    run_migration()
