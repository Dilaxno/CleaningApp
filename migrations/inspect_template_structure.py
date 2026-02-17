"""
Inspect template structure to understand how they're organized
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
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def inspect_templates(db):
    """Inspect template structure"""
    result = db.execute(
        text("SELECT template_id, name, template_data FROM form_templates LIMIT 3")
    )
    templates = result.fetchall()

    for template in templates:
        template_id = template[0]
        template_name = template[1]
        template_data = template[2]

        print(f"\n{'='*60}")
        print(f"Template: {template_name} ({template_id})")
        print(f"{'='*60}")

        if template_data and "sections" in template_data:
            sections = template_data["sections"]
            print(f"Number of sections: {len(sections)}")
            for idx, section in enumerate(sections):
                section_id = section.get("id", "unknown")
                section_title = section.get("title", "unknown")
                fields = section.get("fields", [])
                print(f"\n  Section {idx + 1}: {section_title} (id: {section_id})")
                print(f"  Fields: {len(fields)}")
                for field in fields:
                    field_id = field.get("id", "unknown")
                    field_label = field.get("label", "unknown")
                    field_type = field.get("type", "unknown")
                    print(f"    - {field_id}: {field_label} ({field_type})")
        else:
            print("No sections found")


def main():
    db = SessionLocal()
    try:
        inspect_templates(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
