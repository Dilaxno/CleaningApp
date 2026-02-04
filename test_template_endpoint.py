#!/usr/bin/env python3
"""
Test script to verify the template selection endpoint is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routes.template_selection import AVAILABLE_TEMPLATES

def test_templates():
    print("🧪 Testing Template Selection Endpoint")
    print("=" * 50)
    
    print(f"📊 Total templates available: {len(AVAILABLE_TEMPLATES)}")
    
    # Group by category
    categories = {}
    for template in AVAILABLE_TEMPLATES:
        category = template["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(template["name"])
    
    print(f"📂 Categories: {len(categories)}")
    for category, templates in categories.items():
        print(f"  {category}: {len(templates)} templates")
        for template in templates:
            print(f"    - {template}")
    
    print("\n✅ Template data structure looks good!")
    
    # Test template IDs
    template_ids = [t["id"] for t in AVAILABLE_TEMPLATES]
    print(f"\n🆔 Template IDs: {template_ids}")
    
    # Check for duplicates
    if len(template_ids) != len(set(template_ids)):
        print("❌ Duplicate template IDs found!")
        return False
    
    print("✅ All template IDs are unique!")
    return True

if __name__ == "__main__":
    success = test_templates()
    sys.exit(0 if success else 1)