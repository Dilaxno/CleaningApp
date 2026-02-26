"""
Populate form_templates table with all system templates
Modular architecture with domain-specific template modules

Run with: python -m backend.migrations.populate_form_templates_modular
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from .env file in root directory
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent.parent
env_path = root_dir / ".env"
load_dotenv(env_path)

if not env_path.exists():
    print(f"⚠️  Warning: .env file not found at {env_path}")
    print("Looking for .env in current directory...")
    load_dotenv()
else:
    print(f"✅ Loaded .env from {env_path}")

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

# Import all template modules
from backend.migrations.form_templates import (
    get_office_template,
    get_retail_template,
    get_medical_template,
    get_gym_template,
    get_restaurant_template,
    get_school_template,
    get_warehouse_template,
)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables")
    print("Please set DATABASE_URL in backend/.env file")
    sys.exit(1)

print(f"📊 Using database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def load_scope_templates():
    """Load scope of work templates from JSON file"""
    import json

    scope_file = root_dir / "cleanenroll_scope_of_work_templates.json"
    if not scope_file.exists():
        print(f"⚠️  Warning: Scope templates file not found at {scope_file}")
        return {}

    with open(scope_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert to dict keyed by template name (lowercase for matching)
    scope_templates = {}
    for template in data.get("templates", []):
        template_name = template["name"].lower()
        # Convert serviceAreas to the format expected by frontend
        service_areas = []
        for idx, area in enumerate(template["serviceAreas"]):
            # Generate ID from area name
            area_id = area["name"].lower().replace(" / ", "-").replace(" ", "-")
            service_areas.append(
                {
                    "id": area_id,
                    "name": area["name"],
                    "icon": "🧹",
                    "tasks": [
                        {"id": f"{area_id}-task-{i}", "label": task, "description": None}
                        for i, task in enumerate(area["tasks"])
                    ],
                }
            )

        scope_templates[template_name] = {"serviceAreas": service_areas}

    return scope_templates


# Define minimal FormTemplate model to avoid relationship issues
class FormTemplate(Base):
    __tablename__ = "form_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)
    is_system_template = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    template_data = Column(JSON, nullable=False)
    scope_template = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Define all system templates using modular functions
TEMPLATE_FUNCTIONS = [
    get_office_template,
    get_retail_template,
    get_medical_template,
    get_gym_template,
    get_restaurant_template,
    get_school_template,
    get_warehouse_template,
]


def populate_templates(db: Session):
    """Populate the database with system templates"""
    print("🚀 Starting template population...")
    print(f"📦 Loading {len(TEMPLATE_FUNCTIONS)} template modules...")

    # Load scope templates
    scope_templates = load_scope_templates()
    print(f"📋 Loaded {len(scope_templates)} scope templates")
    print(f"   Available scope templates: {list(scope_templates.keys())}")

    for template_func in TEMPLATE_FUNCTIONS:
        # Get template data from module function
        template_data = template_func()

        # Check if template already exists
        existing = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_data["template_id"],
                FormTemplate.is_system_template,
            )
            .first()
        )

        # Get scope template for this template
        template_id = template_data["template_id"].lower()
        scope_template = scope_templates.get(template_id)

        if scope_template:
            print(f"✅ Found scope template for '{template_data['name']}' (id: {template_id})")
        else:
            print(f"⚠️  No scope template found for '{template_data['name']}' (id: {template_id})")

        if existing:
            print(f"⚠️  Template '{template_data['name']}' already exists, updating...")
            # Update existing template
            existing.name = template_data["name"]
            existing.description = template_data["description"]
            existing.image = template_data["image"]
            existing.color = template_data["color"]
            existing.template_data = template_data["template_data"]
            existing.scope_template = scope_template
        else:
            print(f"✅ Creating template '{template_data['name']}'...")
            # Create new template
            template = FormTemplate(
                template_id=template_data["template_id"],
                user_id=None,
                name=template_data["name"],
                description=template_data["description"],
                image=template_data["image"],
                color=template_data["color"],
                is_system_template=True,
                is_active=True,
                template_data=template_data["template_data"],
                scope_template=scope_template,
            )
            db.add(template)

    db.commit()
    print("✅ Template population complete!")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Form Templates Database Population Script (Modular)")
    print("=" * 60)
    print()

    db = SessionLocal()
    try:
        populate_templates(db)
        print("\n✅ SUCCESS: All templates have been populated in the database")
        print("\nNext steps:")
        print("1. Verify templates in database:")
        print("   SELECT template_id, name FROM form_templates WHERE is_system_template = true;")
        print("2. Test template API endpoints")
        print("3. Update frontend to remove hardcoded templates")
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
