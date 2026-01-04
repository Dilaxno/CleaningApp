"""
Diagnostic script to check BusinessConfig branding settings
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

print("=" * 60)
print("ENVIRONMENT CHECK")
print("=" * 60)
print(f"DATABASE_URL: {'✅ Set' if DATABASE_URL else '❌ Not set'}")
print(f"R2_ACCOUNT_ID: {'✅ Set' if R2_ACCOUNT_ID else '❌ Not set'}")
print(f"R2_ACCESS_KEY_ID: {'✅ Set' if R2_ACCESS_KEY_ID else '❌ Not set'}")
print(f"R2_SECRET_ACCESS_KEY: {'✅ Set' if R2_SECRET_ACCESS_KEY else '❌ Not set'}")
print()

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    print("Please check your .env file is in the correct location")
    sys.exit(1)

try:
    engine = create_engine(DATABASE_URL)
    print("=" * 60)
    print("BUSINESS CONFIG BRANDING DATA")
    print("=" * 60)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                bc.id,
                u.email,
                u.firebase_uid,
                bc.business_name,
                bc.logo_url,
                bc.signature_url
            FROM business_configs bc
            JOIN users u ON bc.user_id = u.id
            ORDER BY bc.id
        """))
        
        rows = result.fetchall()
        
        if not rows:
            print("⚠️  No business configs found")
        else:
            for row in rows:
                print(f"\nConfig ID: {row[0]}")
                print(f"  User Email: {row[1]}")
                print(f"  Firebase UID: {row[2]}")
                print(f"  Business Name: {row[3] or '(not set)'}")
                print(f"  Logo URL: {row[4] or '❌ NOT SET'}")
                print(f"  Signature URL: {row[5] or '❌ NOT SET'}")
        
        print("\n" + "=" * 60)
        print(f"Total configs: {len(rows)}")
        print("=" * 60)
        
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)
