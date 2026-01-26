import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine

def run_migration():
    print("Running migration to add default_brand_color column...")
    
    # SQL command to add the column
    # We use IF NOT EXISTS to make it idempotent (safe to run multiple times)
    # Note: Postgres doesn't support IF NOT EXISTS in ALTER TABLE ADD COLUMN directly in all versions,
    # but we can wrap it in a DO block or catch the error.
    # However, for simplicity and since we know it's missing, we'll try the direct approach first
    # but wrap in try/except to handle if it already exists.
    
    sql = text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_brand_color VARCHAR(7);")
    
    try:
        with engine.connect() as connection:
            connection.execute(sql)
            connection.commit()
            print("✅ Successfully added default_brand_color column to users table.")
    except Exception as e:
        print(f"❌ Error running migration: {e}")

if __name__ == "__main__":
    run_migration()
