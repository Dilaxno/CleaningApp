"""
Run SQL migration to add client limiting columns.
This connects directly to the database and runs the SQL.
"""
import psycopg
from app.config import DATABASE_URL

def run_migration():
    """Add client limiting columns to users table"""
    
    # Convert SQLAlchemy URL to psycopg format (remove driver prefix)
    db_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    
    # SQL to add columns
    sql_commands = [
        """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS clients_this_month INTEGER DEFAULT 0 NOT NULL;
        """,
        """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS month_reset_date TIMESTAMP;
        """,
        """
        UPDATE users 
        SET month_reset_date = DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
        WHERE month_reset_date IS NULL;
        """,
        """
        UPDATE users 
        SET clients_this_month = 0 
        WHERE clients_this_month IS NULL;
        """
    ]
    
    try:
        print("🔄 Connecting to database...")
        print(f"   Using: {db_url[:30]}...")
        # Connect to database
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("✅ Connected!")
                
                for i, sql in enumerate(sql_commands, 1):
                    print(f"📝 Running migration step {i}/{len(sql_commands)}...")
                    cur.execute(sql)
                    print(f"   ✅ Step {i} completed")
                
                conn.commit()
                
                # Verify columns exist
                print("\n🔍 Verifying columns...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name IN ('clients_this_month', 'month_reset_date')
                    ORDER BY column_name;
                """)
                
                columns = cur.fetchall()
                print(f"\n✅ Migration successful! Added columns:")
                for col in columns:
                    print(f"   - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
                
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        raise

if __name__ == "__main__":
    run_migration()
