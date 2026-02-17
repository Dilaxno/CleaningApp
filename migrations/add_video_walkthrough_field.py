"""
Add video walkthrough field to all form templates
Run with: python -m backend.migrations.add_video_walkthrough_field
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

root_dir = Path(__file__).parent.parent.parent
env_path = root_dir / ".env"
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def add_video_walkthrough_field(db):
    """Add videoWalkthrough field to all templates"""
    print("🚀 Starting template update...")

    result = db.execute(text("SELECT id, template_id, name, template_data FROM form_templates"))
    templates = result.fetchall()

    print(f"📋 Found {len(templates)} templates")

    updated_count = 0
    skipped_count = 0

    for template in templates:
        template_id_db = template[0]
        template_id = template[1]
        template_name = template[2]
        template_data = template[3]

        if not template_data or "sections" not in template_data:
            print(f"⚠️  Skipping {template_name} - no sections")
            skipped_count += 1
            continue

        sections = template_data["sections"]
        target_section = None
        target_section_index = None

        for idx, section in enumerate(sections):
            section_id = section.get("id")
            if section_id in ["operations", "service-requirements"]:
                target_section = section
                target_section_index = idx
                break

        if not target_section:
            print(f"⚠️  Skipping {template_name} - no target section")
            skipped_count += 1
            continue

        fields = target_section.get("fields", [])

        has_video = any(field.get("id") == "videoWalkthrough" for field in fields)

        if has_video:
            print(f"✅ {template_name} - already has videoWalkthrough")
            skipped_count += 1
            continue

        special_field_index = None
        for idx, field in enumerate(fields):
            field_id = field.get("id")
            if field_id in ["specialInstructions", "specialRequests"]:
                special_field_index = idx
                break

        if special_field_index is None:
            special_field_index = len(fields)

        video_field = {
            "id": "videoWalkthrough",
            "label": "Video walkthrough (optional)",
            "type": "file",
            "accept": "video/*",
            "required": False,
            "uploadMode": "client-r2",
            "hint": "Upload a video walkthrough of the property for a comprehensive view",
        }

        fields.insert(special_field_index, video_field)
        sections[target_section_index]["fields"] = fields
        template_data["sections"] = sections

        db.execute(
            text("UPDATE form_templates SET template_data = :template_data WHERE id = :id"),
            {"template_data": template_data, "id": template_id_db},
        )

        print(f"✅ Updated {template_name}")
        updated_count += 1

    db.commit()
    print(f"\n✅ Complete! Updated: {updated_count}, Skipped: {skipped_count}")


def main():
    db = SessionLocal()
    try:
        add_video_walkthrough_field(db)
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
