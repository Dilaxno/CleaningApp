import os
import sys
import json
import logging
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    logger.info("Running migration to add new cleaning templates (outside-cleaning, carpet-cleaning)...")
    
    all_templates = [
        "office", "retail", "medical", "gym", "restaurant", "residential", 
        "airbnb", "school", "warehouse", "post-construction", "move-in-out", 
        "deep-clean", "outside-cleaning", "carpet-cleaning"
    ]
    
    sql = text("""
        UPDATE business_configs 
        SET active_templates = CAST(:new_templates AS json)
        WHERE json_array_length(CAST(active_templates AS json)) = 12
        AND CAST(active_templates AS text) LIKE '%"office"%'
        AND CAST(active_templates AS text) LIKE '%"deep-clean"%'
        AND CAST(active_templates AS text) NOT LIKE '%"outside-cleaning"%'
        AND CAST(active_templates AS text) NOT LIKE '%"carpet-cleaning"%';
    """)
    
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, {"new_templates": json.dumps(all_templates)})
            connection.commit()
            rows_updated = result.rowcount
            logger.info(f"✅ Successfully updated {rows_updated} business configs with new cleaning templates.")
            
            sql_empty = text("""
                UPDATE business_configs 
                SET active_templates = CAST(:new_templates AS json)
                WHERE active_templates IS NULL 
                OR CAST(active_templates AS text) = '[]'
                OR json_array_length(CAST(active_templates AS json)) = 0;
            """)
            
            result_empty = connection.execute(sql_empty, {"new_templates": json.dumps(all_templates)})
            connection.commit()
            rows_empty = result_empty.rowcount
            logger.info(f"✅ Successfully set default templates for {rows_empty} business configs with empty templates.")
            
            logger.info(f"\n🎉 Migration completed successfully!")
            logger.info(f"   - Updated {rows_updated} existing configs")
            logger.info(f"   - Set defaults for {rows_empty} empty configs")
            
    except Exception as e:
        logger.error(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()