      add_video_walkthrough_field(db)
        print("\n✅ SUCCESS: All templates have been updated")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
  {"template_data": template_data, "id": template_id_db},
        )

        print(f"✅ Updated {template_name} - added videoWalkthrough field")
        updated_count += 1

    db.commit()
    print(f"\n✅ Update complete!")
    print(f"   - Updated: {updated_count} templates")
    print(f"   - Skipped: {skipped_count} templates")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Add Video Walkthrough Field to Templates")
    print("=" * 60)
    print()

    db = SessionLocal()
    try:
  dMode": "client-r2",
            "hint": "Upload a video walkthrough of the property for a comprehensive view",
        }

        # Insert before special field
        fields.insert(special_field_index, video_walkthrough_field)

        # Update the section
        sections[target_section_index]["fields"] = fields
        template_data["sections"] = sections

        # Update in database
        db.execute(
            text("UPDATE form_templates SET template_data = :template_data WHERE id = :id"),
          t("id")
            if field_id in ["specialInstructions", "specialRequests"]:
                special_field_index = idx
                break

        if special_field_index is None:
            special_field_index = len(fields)

        # Create the videoWalkthrough field
        video_walkthrough_field = {
            "id": "videoWalkthrough",
            "label": "Video walkthrough (optional)",
            "type": "file",
            "accept": "video/*",
            "required": False,
            "uploat_section.get("fields", [])

        # Check if videoWalkthrough already exists
        has_video_walkthrough = any(field.get("id") == "videoWalkthrough" for field in fields)

        if has_video_walkthrough:
            print(f"✅ {template_name} - videoWalkthrough already exists")
            skipped_count += 1
            continue

        # Find the specialInstructions or specialRequests field index
        special_field_index = None
        for idx, field in enumerate(fields):
            field_id = field.geone

        # Find either operations or service-requirements section
        for idx, section in enumerate(sections):
            section_id = section.get("id")
            if section_id in ["operations", "service-requirements"]:
                target_section = section
                target_section_index = idx
                break

        if not target_section:
            print(f"⚠️  Skipping {template_name} - no target section found")
            skipped_count += 1
            continue

        fields = targe   updated_count = 0
    skipped_count = 0

    for template in templates:
        template_id_db = template[0]
        template_id = template[1]
        template_name = template[2]
        template_data = template[3]

        if not template_data or "sections" not in template_data:
            print(f"⚠️  Skipping {template_name} - no sections found")
            skipped_count += 1
            continue

        sections = template_data["sections"]
        target_section = None
        target_section_index = Ne DATABASE_URL}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def add_video_walkthrough_field(db):
    """Add videoWalkthrough field to all templates before specialRequests/specialInstructions"""
    print("🚀 Starting template update...")

    result = db.execute(text("SELECT id, template_id, name, template_data FROM form_templates"))
    templates = result.fetchall()

    print(f"📋 Found {len(templates)} templates to update")

 ile__).parent.parent.parent))

root_dir = Path(__file__).parent.parent.parent
env_path = root_dir / ".env"
load_dotenv(env_path)

if not env_path.exists():
    print(f"⚠️  Warning: .env file not found at {env_path}")
    load_dotenv()
else:
    print(f"✅ Loaded .env from {env_path}")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

print(f"📊 Using database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL elsine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__freate_engort c.migrations.add_video_walkthrough_to_templates
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy imp templates
This updates existing templates in the database to include the videoWalkthrough field

Run with: python -m backend"""
