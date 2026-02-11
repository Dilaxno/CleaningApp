#!/usr/bin/env python3
"""
Script to insert missing templates into form_templates table
"""

from app.database import SessionLocal
from sqlalchemy import text

def insert_templates():
    db = SessionLocal()
    
    try:
        print("🔍 Inserting missing templates into form_templates table...\n")
        
        # Check current template count
        result = db.execute(text("""
            SELECT COUNT(*) FROM form_templates WHERE is_system_template = true
        """))
        current_count = result.fetchone()[0]
        print(f"Current system templates: {current_count}")
        
        # Insert Outside Cleaning template
        print("\n1️⃣ Inserting 'outside-cleaning' template...")
        try:
            db.execute(text("""
                INSERT INTO form_templates (
                    template_id,
                    user_id,
                    name,
                    description,
                    image,
                    color,
                    is_system_template,
                    is_active,
                    template_data
                ) VALUES (
                    'outside-cleaning',
                    NULL,
                    'Outside Cleaning',
                    'Exterior cleaning services for buildings and outdoor spaces.',
                    'https://res.cloudinary.com/dxqum9ywx/image/upload/v1770247865/outside_cleaning_acgpg4.jpg',
                    '#1a1a1a',
                    true,
                    true,
                    '{}'
                )
                ON CONFLICT (template_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    image = EXCLUDED.image
            """))
            db.commit()
            print("   ✅ Successfully inserted 'outside-cleaning'")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            db.rollback()
        
        # Insert Carpet Cleaning template
        print("\n2️⃣ Inserting 'carpet-cleaning' template...")
        try:
            db.execute(text("""
                INSERT INTO form_templates (
                    template_id,
                    user_id,
                    name,
                    description,
                    image,
                    color,
                    is_system_template,
                    is_active,
                    template_data
                ) VALUES (
                    'carpet-cleaning',
                    NULL,
                    'Carpet Cleaning',
                    'Professional carpet and upholstery cleaning services.',
                    'https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80',
                    '#1a1a1a',
                    true,
                    true,
                    '{}'
                )
                ON CONFLICT (template_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    image = EXCLUDED.image
            """))
            db.commit()
            print("   ✅ Successfully inserted 'carpet-cleaning'")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            db.rollback()
        
        # Check final count
        result = db.execute(text("""
            SELECT COUNT(*) FROM form_templates WHERE is_system_template = true
        """))
        final_count = result.fetchone()[0]
        
        print(f"\n{'='*80}")
        print(f"✅ Migration completed!")
        print(f"   - Before: {current_count} templates")
        print(f"   - After: {final_count} templates")
        print(f"   - Added: {final_count - current_count} templates")
        print(f"{'='*80}\n")
        
        # List all templates
        print("📋 All system templates:")
        result = db.execute(text("""
            SELECT template_id, name 
            FROM form_templates 
            WHERE is_system_template = true
            ORDER BY template_id
        """))
        
        for template_id, name in result.fetchall():
            print(f"   - {template_id}: {name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    insert_templates()
