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
    
    # For PostgreSQL with JSON type (not JSONB), use json_array_length and CAST
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
            print(f"✅ Successfully updated {rows_updated} business configs with new cleaning templates.")
            
            # Also update any configs that are empty or null (backward compatibility)
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
            print(f"✅ Successfully set default templates for {rows_empty} business configs with empty templates.")
            
            print(f"\n🎉 Migration completed successfully!")
            print(f"   - Updated {rows_updated} existing configs")
            print(f"   - Set defaults for {rows_empty} empty configs")
            
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()