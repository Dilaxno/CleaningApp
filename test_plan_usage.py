"""
Test script to check plan usage endpoint and data
"""
from app.database import SessionLocal
from app.models import User
from app.plan_limits import get_usage_stats

def test_plan_usage():
    db = SessionLocal()
    try:
        # Get first user to test
        users = db.query(User).all()
        
        if not users:
            print("❌ No users found in database")
            return
        
        print(f"📊 Testing plan usage for {len(users)} user(s):\n")
        
        for user in users[:3]:  # Test first 3 users
            print(f"User: {user.full_name or user.email}")
            print(f"  Plan: {user.plan}")
            print(f"  Clients this month: {user.clients_this_month}")
            print(f"  Month reset date: {user.month_reset_date}")
            
            # Get usage stats
            stats = get_usage_stats(user, db)
            print(f"  Usage stats: {stats}")
            print()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_plan_usage()
