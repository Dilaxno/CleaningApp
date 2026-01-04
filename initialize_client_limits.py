"""
Initialize client limiting fields for existing users.
Run this script once to set up the new fields for existing users.
"""
from datetime import datetime
from app.database import SessionLocal
from app.models import User

def initialize_client_limits():
    db = SessionLocal()
    try:
        # Get all users
        users = db.query(User).all()
        
        now = datetime.utcnow()
        # Set next reset date to first day of next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        
        updated_count = 0
        for user in users:
            # Initialize fields if they're None
            if user.clients_this_month is None:
                user.clients_this_month = 0
                updated_count += 1
            
            if user.month_reset_date is None:
                user.month_reset_date = next_month
                updated_count += 1
        
        db.commit()
        print(f"✅ Initialized client limiting fields for {len(users)} users")
        print(f"   Updated {updated_count} field values")
        print(f"   Reset date set to: {next_month}")
        
    except Exception as e:
        print(f"❌ Error initializing client limits: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    initialize_client_limits()
