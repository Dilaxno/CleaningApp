"""
Migration script to add missing columns to the users table.
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
        # Check and add onboarding_completed column
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'onboarding_completed'
        """))
        
        if not result.fetchone():
            print("🔄 Adding onboarding_completed column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("✅ Added onboarding_completed column")
        else:
            print("✅ onboarding_completed column already exists")
        
        # Check and add updated_at column
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'updated_at'
        """))
        
        if not result.fetchone():
            print("🔄 Adding updated_at column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()"))
            conn.commit()
            print("✅ Added updated_at column")
        else:
            print("✅ updated_at column already exists")

        print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
