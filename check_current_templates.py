#!/usr/bin/env python3
"""
Script to check current template state in database
"""

from app.database import SessionLocal
from sqlalchemy import text
import json

def check_templates():
    db = SessionLocal()
    
    try:
        print("🔍 Checking current template state...\n")
        
        # Check all business configs
        result = db.execute(text("""
            SELECT 
                u.email,
                u.firebase_uid,
                bc.active_templates,
                CASE 
                    WHEN bc.active_templates IS NULL THEN 'NULL'
                    WHEN CAST(bc.active_templates AS text) = '[]' THEN 'EMPTY'
                    ELSE 'HAS_DATA'
                END as status
            FROM business_configs bc
            JOIN users u ON u.id = bc.user_id
            ORDER BY bc.created_at DESC
        """))
        
        configs = result.fetchall()
        
        if not configs:
            print("❌ No business configs found!")
            return
        
        print(f"Found {len(configs)} business config(s):\n")
        
        for email, uid, templates, status in configs:
            print(f"{'='*80}")
            print(f"User: {email}")
            print(f"Firebase UID: {uid}")
            print(f"Status: {status}")
            
            if templates:
                try:
                    # Parse JSON
                    if isinstance(templates, str):
                        template_list = json.loads(templates)
                    else:
                        template_list = templates
                    
                    print(f"Template count: {len(template_list)}")
                    print(f"Templates: {template_list}")
                    
                    # Check for missing templates
                    has_outside = 'outside-cleaning' in template_list
                    has_carpet = 'carpet-cleaning' in template_list
                    
                    print(f"\nMissing templates:")
                    if not has_outside:
                        print(f"  ❌ outside-cleaning")
                    else:
                        print(f"  ✅ outside-cleaning")
                    
                    if not has_carpet:
                        print(f"  ❌ carpet-cleaning")
                    else:
                        print(f"  ✅ carpet-cleaning")
                        
                except Exception as e:
                    print(f"Error parsing templates: {e}")
                    print(f"Raw value: {templates}")
            else:
                print(f"Templates: {templates}")
            
            print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_templates()
