#!/usr/bin/env python3
"""
Script to verify active templates in the database
Usage: python verify_templates.py [email]
"""

import sys
from app.database import SessionLocal
from app.models import User, BusinessConfig
from app.routes.template_selection import AVAILABLE_TEMPLATES

def verify_templates(email=None):
    """Verify active templates for a user or all users"""
    db = SessionLocal()
    
    try:
        # Get all available template IDs
        available_ids = [t["id"] for t in AVAILABLE_TEMPLATES]
        print(f"\n📋 Available Templates ({len(available_ids)}):")
        for template in AVAILABLE_TEMPLATES:
            print(f"  - {template['id']}: {template['name']}")
        
        # Query users
        if email:
            users = db.query(User).filter(User.email == email).all()
            if not users:
                print(f"\n❌ No user found with email: {email}")
                return
        else:
            users = db.query(User).all()
        
        print(f"\n👥 Checking {len(users)} user(s)...\n")
        
        for user in users:
            config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
            
            print(f"{'='*80}")
            print(f"User: {user.email}")
            print(f"Firebase UID: {user.firebase_uid}")
            print(f"Onboarding Complete: {user.onboarding_completed}")
            
            if config:
                active = config.active_templates or []
                print(f"\n✅ Business Config Found:")
                print(f"  - Onboarding Complete: {config.onboarding_complete}")
                print(f"  - Active Templates: {len(active)} selected")
                
                if active:
                    print(f"\n  Selected Templates:")
                    for template_id in active:
                        # Find template name
                        template = next((t for t in AVAILABLE_TEMPLATES if t["id"] == template_id), None)
                        if template:
                            print(f"    ✓ {template_id}: {template['name']}")
                        else:
                            print(f"    ⚠️  {template_id}: UNKNOWN TEMPLATE")
                    
                    # Check for specific templates
                    has_outside = "outside-cleaning" in active
                    has_carpet = "carpet-cleaning" in active
                    
                    print(f"\n  Specific Templates:")
                    print(f"    - Outside Cleaning: {'✓ YES' if has_outside else '✗ NO'}")
                    print(f"    - Carpet Cleaning: {'✓ YES' if has_carpet else '✗ NO'}")
                    
                    # Check for invalid IDs
                    invalid = [tid for tid in active if tid not in available_ids]
                    if invalid:
                        print(f"\n  ⚠️  Invalid Template IDs: {invalid}")
                else:
                    print(f"\n  ⚠️  No templates selected (empty array)")
                    print(f"  💡 This means ALL templates will be shown to clients (backward compatibility)")
            else:
                print(f"\n❌ No Business Config Found")
                print(f"  💡 User has not completed onboarding")
            
            print(f"{'='*80}\n")
    
    finally:
        db.close()

def main():
    """Main entry point"""
    email = sys.argv[1] if len(sys.argv) > 1 else None
    
    if email:
        print(f"🔍 Verifying templates for: {email}")
    else:
        print(f"🔍 Verifying templates for ALL users")
    
    verify_templates(email)

if __name__ == "__main__":
    main()
