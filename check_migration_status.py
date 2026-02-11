#!/usr/bin/env python3
"""
Script to check if active_templates migrations have been applied
Usage: python check_migration_status.py
PostgreSQL version
"""

from app.database import SessionLocal
from sqlalchemy import text

def check_migration_status():
    """Check if active_templates column exists and has data"""
    db = SessionLocal()
    
    try:
        print("🔍 Checking active_templates migration status...\n")
        
        # Check if column exists
        print("1️⃣ Checking if active_templates column exists...")
        try:
            result = db.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'business_configs'
                AND column_name = 'active_templates'
            """))
            column_info = result.fetchone()
            
            if column_info:
                print(f"   ✅ Column exists!")
                print(f"   - Name: {column_info[0]}")
                print(f"   - Type: {column_info[1]}")
                print(f"   - Default: {column_info[2]}")
            else:
                print(f"   ❌ Column does NOT exist!")
                print(f"   💡 Run migration: backend/migrations/add_active_templates.sql")
                return
        except Exception as e:
            print(f"   ❌ Error checking column: {e}")
            return
        
        # Check data in column
        print(f"\n2️⃣ Checking active_templates data...")
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_configs,
                COUNT(CASE WHEN active_templates IS NULL THEN 1 END) as null_count,
                COUNT(CASE WHEN active_templates = '[]'::jsonb THEN 1 END) as empty_count,
                COUNT(CASE WHEN jsonb_array_length(active_templates) > 0 THEN 1 END) as has_templates,
                COUNT(CASE WHEN active_templates @> '"outside-cleaning"'::jsonb THEN 1 END) as has_outside,
                COUNT(CASE WHEN active_templates @> '"carpet-cleaning"'::jsonb THEN 1 END) as has_carpet
            FROM business_configs
        """))
        stats = result.fetchone()
        
        print(f"   📊 Statistics:")
        print(f"   - Total configs: {stats[0]}")
        print(f"   - NULL values: {stats[1]}")
        print(f"   - Empty arrays: {stats[2]}")
        print(f"   - With templates: {stats[3]}")
        print(f"   - Has 'outside-cleaning': {stats[4]}")
        print(f"   - Has 'carpet-cleaning': {stats[5]}")
        
        # Check for configs missing new templates
        print(f"\n3️⃣ Checking for configs missing new templates...")
        result = db.execute(text("""
            SELECT 
                u.email,
                u.firebase_uid,
                bc.active_templates,
                jsonb_array_length(bc.active_templates) as template_count
            FROM business_configs bc
            JOIN users u ON u.id = bc.user_id
            WHERE bc.active_templates IS NOT NULL
            AND jsonb_array_length(bc.active_templates) > 0
            AND (
                NOT bc.active_templates @> '"outside-cleaning"'::jsonb
                OR NOT bc.active_templates @> '"carpet-cleaning"'::jsonb
            )
            ORDER BY bc.created_at DESC
            LIMIT 10
        """))
        
        missing = result.fetchall()
        if missing:
            print(f"   ⚠️  Found {len(missing)} configs missing new templates:")
            for row in missing:
                email, uid, templates, count = row
                has_outside = 'outside-cleaning' in str(templates)
                has_carpet = 'carpet-cleaning' in str(templates)
                print(f"\n   User: {email}")
                print(f"   - Firebase UID: {uid}")
                print(f"   - Template count: {count}")
                print(f"   - Has outside-cleaning: {'✓' if has_outside else '✗'}")
                print(f"   - Has carpet-cleaning: {'✓' if has_carpet else '✗'}")
        else:
            print(f"   ✅ All configs have the new templates!")
        
        # Check for configs that need migration
        print(f"\n4️⃣ Checking for configs that need migration...")
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM business_configs
            WHERE active_templates IS NULL 
            OR active_templates = '[]'::jsonb
            OR jsonb_array_length(active_templates) = 0
        """))
        needs_migration = result.fetchone()[0]
        
        if needs_migration > 0:
            print(f"   ⚠️  {needs_migration} configs need migration (NULL or empty)")
            print(f"   💡 Run migration: backend/migrations/add_new_cleaning_templates.sql")
        else:
            print(f"   ✅ No configs need migration!")
        
        print(f"\n{'='*80}")
        print(f"✅ Migration check complete!")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n❌ Error during migration check: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_migration_status()
