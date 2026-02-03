#!/usr/bin/env python3
"""
Run the service areas migration to add the service_areas column to business_configs table.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the app directory to the path so we can import from it
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

def run_migration():
    """Run the service areas migration."""
    engine = create_engine(DATABASE_URL)
    
    migration_sql = """
    -- Add service area configuration to business_configs table
    ALTER TABLE business_configs 
    ADD COLUMN IF NOT EXISTS service_areas JSON DEFAULT '[]';
    
    -- Add comment for documentation
    COMMENT ON COLUMN business_configs.service_areas IS 'JSON array of service areas with states, counties, and neighborhoods. Format: [{"type": "state", "value": "CA", "name": "California"}, {"type": "county", "value": "Los Angeles County", "state": "CA"}, {"type": "neighborhood", "value": "Beverly Hills", "state": "CA", "county": "Los Angeles County"}]';
    """
    
    try:
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(migration_sql))
            conn.commit()
            print("✅ Service areas migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)