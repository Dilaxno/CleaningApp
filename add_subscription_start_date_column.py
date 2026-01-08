"""
Migration script to add subscription_start_date column to users table.
This column tracks when the subscription started for billing cycle calculations.
Usage resets 30 days from subscription date, not on the first of the month.
"""
from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        # Add subscription_start_date column
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS subscription_start_date TIMESTAMP;
        """))
        
        # For existing users with a plan, set subscription_start_date to their created_at
        # This ensures existing users have a baseline for billing cycle calculations
        conn.execute(text("""
            UPDATE users 
            SET subscription_start_date = created_at 
            WHERE plan IS NOT NULL AND subscription_start_date IS NULL;
        """))
        
        # Recalculate month_reset_date for existing users based on subscription_start_date
        # Reset date should be 30 days from subscription anniversary, not first of month
        conn.execute(text("""
            UPDATE users 
            SET month_reset_date = subscription_start_date + INTERVAL '30 days'
            WHERE subscription_start_date IS NOT NULL 
            AND month_reset_date IS NOT NULL;
        """))
        
        conn.commit()
        print("✅ Migration complete: Added subscription_start_date column")
        print("   - Existing users with plans: subscription_start_date set to created_at")
        print("   - month_reset_date recalculated to 30 days from subscription date")

if __name__ == "__main__":
    migrate()
