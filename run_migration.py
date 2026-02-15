"""
Generic migration runner script
Usage: python run_migration.py <migration_file.sql>
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_migration(migration_file_path: str):
    """Run a SQL migration file"""
    migration_file = Path(migration_file_path)
    
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        sys.exit(1)
    
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
    if len(sys.argv) < 2:
        logger.error("Usage: python run_migration.py <migration_file.sql>")
        sys.exit(1)
    
    try:
        run_migration(sys.argv[1])
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
