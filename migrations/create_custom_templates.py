import os
import sys

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine
from sqlalchemy import text

def run_migration():
    print("Creating custom_templates table...")
    
    sql = text("""
    CREATE TABLE IF NOT EXISTS custom_templates (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        base_template_id VARCHAR(50) NOT NULL,
        name VARCHAR(255) NOT NULL,
        description VARCHAR(1000),
        template_config JSONB NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    
    index_sql = [
        text("CREATE INDEX IF NOT EXISTS idx_custom_templates_user_id ON custom_templates(user_id);"),
        text("CREATE INDEX IF NOT EXISTS idx_custom_templates_base_template ON custom_templates(base_template_id);"),
        text("CREATE INDEX IF NOT EXISTS idx_custom_templates_active ON custom_templates(is_active);")
    ]
    
    try:
        with engine.connect() as connection:
            connection.execute(sql)
            for idx_sql in index_sql:
                connection.execute(idx_sql)
            connection.commit()
            print("✅ Successfully created custom_templates table and indexes.")
    except Exception as e:
        print(f"❌ Error running migration: {e}")

if __name__ == "__main__":
    run_migration()