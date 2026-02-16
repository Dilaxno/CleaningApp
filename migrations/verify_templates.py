"""
Verify that templates have been populated correctly
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root
root_dir = Path(__file__).parent.parent.parent
load_dotenv(root_dir / ".env")

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found")
    exit(1)

# Convert SQLAlchemy URL to psycopg2 format
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
elif DATABASE_URL.startswith("postgres+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgres+psycopg://", "postgresql://")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check template count
    cursor.execute("""
        SELECT COUNT(*) 
        FROM form_templates 
        WHERE is_system_template = true
    """)
    count = cursor.fetchone()[0]
    print(f"📊 Found {count} system template(s)")
    print()
    
    # Get template details
    cursor.execute("""
        SELECT 
            template_id,
            name,
            json_array_length(template_data->'sections') as section_count,
            (template_data->'sections'->0->>'title') as first_section
        FROM form_templates 
        WHERE is_system_template = true
        ORDER BY template_id
    """)
    
    rows = cursor.fetchall()
    
    print("Template Details:")
    print("-" * 80)
    print(f"{'Template ID':<20} {'Name':<30} {'Sections':<10} {'First Section':<20}")
    print("-" * 80)
    
    for row in rows:
        template_id, name, sections, first_section = row
        print(f"{template_id:<20} {name:<30} {sections:<10} {first_section or 'N/A':<20}")
    
    print("-" * 80)
    print()
    
    # Check if sections have fields
    cursor.execute("""
        SELECT 
            template_id,
            json_array_length(template_data->'sections'->0->'fields') as field_count
        FROM form_templates 
        WHERE is_system_template = true
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    if result:
        template_id, field_count = result
        print(f"✅ Template '{template_id}' has {field_count} fields in first section")
    
    cursor.close()
    conn.close()
    
    if count == 0:
        print("\n⚠️  No templates found! Run the migration script:")
        print("   python -m backend.migrations.populate_form_templates")
    elif count == 1:
        print("\n⚠️  Only 1 template found. You need to add the remaining 13 templates.")
        print("   Edit backend/migrations/populate_form_templates.py")
    else:
        print(f"\n✅ SUCCESS: {count} templates are in the database!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
