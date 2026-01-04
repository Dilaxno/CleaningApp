"""
Migration script to rename clerk_id column to firebase_uid in the users table.
Run this once to update your Neon database schema.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if clerk_id column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'clerk_id'
        """))
        
        if result.fetchone():
            print("🔄 Renaming clerk_id to firebase_uid...")
            conn.execute(text("ALTER TABLE users RENAME COLUMN clerk_id TO firebase_uid"))
            conn.commit()
            print("✅ Migration complete! Column renamed to firebase_uid")
        else:
            # Check if firebase_uid already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'firebase_uid'
            """))
            
            if result.fetchone():
                print("✅ Column firebase_uid already exists. No migration needed.")
            else:
                print("⚠️ Neither clerk_id nor firebase_uid found. Creating firebase_uid column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(255) UNIQUE"))
                conn.commit()
                print("✅ Created firebase_uid column")

if __name__ == "__main__":
    migrate()
