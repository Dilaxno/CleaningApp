import os
import sys
import json
from sqlalchemy import text

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine

def run_migration():
    print("Running migration to add new cleaning templates (outside-cleaning, carpet-cleaning)...")
    
    # Updated template list with new templates
    all_templates = [
        "office", "retail", "medical", "gym", "restaurant", "residential", 
        "airbnb", "school", "warehouse", "post-construction", "move-in-out", 
        "deep-clean", "outside-cleaning", "carpet-cleaning"
    ]
    
    # For SQLite, we need to use different JSON functions
    # First, let's update configs that have exactly 12 templates (the old complete set)
    sql = text("""
        UPDATE business_configs 
        SET active_templates = :new_templates
        WHERE json_array_length(active_templates) = 12
        AND json_extract(active_templates, '$') LIKE '%"office"%'
        AND json_extract(active_templates, '$') LIKE '%"deep-clean"%'
        AND json_extract(active_templates, '$') NOT LIKE '%"outside-cleaning"%'
        AND json_extract(active_templates, '$') NOT LIKE '%"carpet-cleaning"%';
    """)
    
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, {"new_templates": json.dumps(all_templates)})
            connection.commit()
            rows_updated = result.rowcount
            print(f"✅ Successfully updated {rows_updated} business configs with new cleaning templates.")
            
            # Also update any configs that are empty or null (backward compatibility)
            sql_empty = text("""
                UPDATE business_configs 
                SET active_templates = :new_templates
                WHERE active_templates IS NULL 
                OR active_templates = '[]' 
                OR json_array_length(active_templates) = 0;
            """)
            
            result_empty = connection.execute(sql_empty, {"new_templates": json.dumps(all_templates)})
            connection.commit()
            rows_empty = result_empty.rowcount
            print(f"✅ Successfully set default templates for {rows_empty} business configs with empty templates.")
            
    except Exception as e:
        print(f"❌ Error running migration: {e}")

if __name__ == "__main__":
    run_migration()