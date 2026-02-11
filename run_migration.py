"""
Run custom quote requests migration
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text

def run_migration():
    """Run the custom quote requests migration"""
    migration_file = Path(__file__).parent / "migrations" / "add_custom_quote_requests.sql"
    
    print(f"Reading migration file: {migration_file}")
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    # Split by semicolon and filter empty statements
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    print(f"Found {len(statements)} SQL statements to execute")
    
    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            print(f"Executing statement {i}/{len(statements)}...")
            conn.execute(text(stmt))
        conn.commit()
    
    print("✅ Migration completed successfully!")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
