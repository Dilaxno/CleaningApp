"""
Helper script to generate template data from existing TypeScript templates
This reads the TypeScript files and converts them to Python dictionaries

Usage: python backend/migrations/template_data_generator.py
"""

import json
import re
from pathlib import Path


def extract_template_from_ts(file_path: Path, template_name: str):
    """Extract template data from TypeScript file"""
    content = file_path.read_text()
    
    # Find the template export
    pattern = rf"export const {template_name}:\s*FormTemplate\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print(f"❌ Could not find template {template_name} in {file_path}")
        return None
    
    template_str = match.group(1)
    
    # Extract basic info
    id_match = re.search(r'id:\s*"([^"]+)"', template_str)
    name_match = re.search(r'name:\s*"([^"]+)"', template_str)
    desc_match = re.search(r'description:\s*"([^"]+)"', template_str)
    image_match = re.search(r'image:\s*"([^"]+)"', template_str)
    color_match = re.search(r'color:\s*"([^"]+)"', template_str)
    
    if not all([id_match, name_match]):
        print(f"❌ Missing required fields in {template_name}")
        return None
    
    template_data = {
        "template_id": id_match.group(1),
        "name": name_match.group(1),
        "description": desc_match.group(1) if desc_match else "",
        "image": image_match.group(1) if image_match else "",
        "color": color_match.group(1) if color_match else "#1a1a1a",
    }
    
    print(f"✅ Extracted {template_name}: {template_data['name']}")
    return template_data


def main():
    """Main function to extract all templates"""
    frontend_path = Path("frontend/src/pages/ClientForm/templates")
    
    if not frontend_path.exists():
        print(f"❌ Frontend templates directory not found: {frontend_path}")
        return
    
    templates = []
    
    # Commercial templates
    commercial_file = frontend_path / "commercial.ts"
    if commercial_file.exists():
        templates.append(extract_template_from_ts(commercial_file, "officeCommercialTemplate"))
        templates.append(extract_template_from_ts(commercial_file, "retailTemplate"))
        templates.append(extract_template_from_ts(commercial_file, "warehouseTemplate"))
    
    # Healthcare templates
    healthcare_file = frontend_path / "healthcare.ts"
    if healthcare_file.exists():
        templates.append(extract_template_from_ts(healthcare_file, "medicalTemplate"))
        templates.append(extract_template_from_ts(healthcare_file, "gymTemplate"))
    
    # Hospitality templates
    hospitality_file = frontend_path / "hospitality.ts"
    if hospitality_file.exists():
        templates.append(extract_template_from_ts(hospitality_file, "restaurantTemplate"))
    
    # Residential templates
    residential_file = frontend_path / "residential.ts"
    if residential_file.exists():
        templates.append(extract_template_from_ts(residential_file, "residentialTemplate"))
        templates.append(extract_template_from_ts(residential_file, "airbnbTemplate"))
    
    # Education templates
    education_file = frontend_path / "education.ts"
    if education_file.exists():
        templates.append(extract_template_from_ts(education_file, "schoolTemplate"))
    
    # Specialized templates
    specialized_file = frontend_path / "specialized.ts"
    if specialized_file.exists():
        templates.append(extract_template_from_ts(specialized_file, "postConstructionTemplate"))
        templates.append(extract_template_from_ts(specialized_file, "moveInOutTemplate"))
        templates.append(extract_template_from_ts(specialized_file, "deepCleanTemplate"))
        templates.append(extract_template_from_ts(specialized_file, "outsideCleaningTemplate"))
        templates.append(extract_template_from_ts(specialized_file, "carpetCleaningTemplate"))
    
    # Filter out None values
    templates = [t for t in templates if t is not None]
    
    print(f"\n✅ Extracted {len(templates)} templates")
    print("\nTemplate IDs:")
    for t in templates:
        print(f"  - {t['template_id']}: {t['name']}")
    
    # Save to JSON file for reference
    output_file = Path("backend/migrations/extracted_templates.json")
    output_file.write_text(json.dumps(templates, indent=2))
    print(f"\n✅ Saved template metadata to {output_file}")


if __name__ == "__main__":
    main()
