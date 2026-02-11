"""
Run custom quote requests migration
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Run the custom quote requests migration"""
    migration_file = Path(__file__).parent / "migrations" / "add_custom_quote_requests.sql"
    
    logger.info(f"Reading migration file: {migration_file}")
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    logger.info(f"Found {len(statements)} SQL statements to execute")
    
    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            logger.info(f"Executing statement {i}/{len(statements)}...")
            conn.execute(text(stmt))
        conn.commit()
    
    logger.info("✅ Migration completed successfully!")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
