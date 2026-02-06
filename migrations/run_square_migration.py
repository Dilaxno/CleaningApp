"""
Run Square Integration Migration
Creates the square_integrations table
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from root directory
root_dir = Path(__file__).parent.parent.parent
env_file = root_dir / ".env"

if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment from: {env_file}")
else:
    print(f"⚠️  No .env file found at: {env_file}")
    load_dotenv()  # Try default locations

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    print(f"   Checked: {env_file}")
    sys.exit(1)

def run_migration():
    """Run the Square integration migration"""
    engine = create_engine(DATABASE_URL)
    
    # Read SQL file
    sql_file = Path(__file__).parent / "add_square_integration_clean.sql"
    with open(sql_file, 'r') as f:
        sql = f.read()
    
    try:
        with engine.connect() as conn:
            # Execute migration
            conn.execute(text(sql))
            conn.commit()
            print("✅ Square integration table created successfully")
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("Running Square integration migration...")
    run_migration()
