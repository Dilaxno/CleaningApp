"""
Fix signature URLs that were stored as presigned URLs instead of R2 keys
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import re

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# Pattern to match presigned URLs and extract the R2 key
# Example: https://...r2.cloudflarestorage.com/cleanenroll/signatures/uid/file.png?X-Amz-...
presigned_url_pattern = r'https://[^/]+\.r2\.cloudflarestorage\.com/[^/]+/(.+?)\?'

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, user_id, business_name, signature_url 
        FROM business_configs 
        WHERE signature_url IS NOT NULL
    """))
    
    rows = result.fetchall()
    fixed_count = 0
    
    for row in rows:
        config_id, user_id, business_name, signature_url = row
        
        # Check if this is a presigned URL
        if signature_url and 'r2.cloudflarestorage.com' in signature_url and '?' in signature_url:
            # Extract the key from the presigned URL
            match = re.search(presigned_url_pattern, signature_url)
            if match:
                key = match.group(1)
                print(f"\n🔧 Fixing signature URL for: {business_name or 'Config ' + str(config_id)}")
                print(f"   Old (presigned URL): {signature_url[:80]}...")
                print(f"   New (R2 key): {key}")
                
                # Update the database
                conn.execute(
                    text("UPDATE business_configs SET signature_url = :key WHERE id = :id"),
                    {"key": key, "id": config_id}
                )
                conn.commit()
                fixed_count += 1
            else:
                print(f"⚠️  Could not parse presigned URL for config {config_id}")
        elif signature_url and signature_url.startswith('signatures/'):
            print(f"✅ Already correct: {business_name or 'Config ' + str(config_id)}")

print(f"\n{'='*60}")
print(f"✅ Fixed {fixed_count} signature URL(s)")
print(f"{'='*60}")
