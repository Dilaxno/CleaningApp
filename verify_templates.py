#!/usr/bin/env python3
"""
Script to verify active templates in the database
Usage: python verify_templates.py [email]
"""

import sys
import logging
from app.database import SessionLocal
from app.models import User, BusinessConfig
from app.routes.template_selection import AVAILABLE_TEMPLATES

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_templates(email=None):
    """Verify active templates for a user or all users"""
    db = SessionLocal()
    
    try:
        # Get all available template IDs
        available_ids = [t["id"] for t in AVAILABLE_TEMPLATES]
        logger.info(f"\n📋 Available Templates ({len(available_ids)}):")
        for template in AVAILABLE_TEMPLATES:
            logger.info(f"  - {template['id']}: {template['name']}")
        
        # Query users
        if email:
            users = db.query(User).filter(User.email == email).all()
            if not users:
                logger.error(f"\n❌ No user found with email: {email}")
                return
        else:
            users = db.query(User).all()
        
        logger.info(f"\n👥 Checking {len(users)} user(s)...\n")
        
        for user in users:
            config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
            
            logger.info(f"{'='*80}")
            logger.info(f"User: {user.email}")
            logger.info(f"Firebase UID: {user.firebase_uid}")
            logger.info(f"Onboarding Complete: {user.onboarding_completed}")
            
            if config:
                active = config.active_templates or []
                logger.info(f"\n✅ Business Config Found:")
                logger.info(f"  - Onboarding Complete: {config.onboarding_complete}")
                logger.info(f"  - Active Templates: {len(active)} selected")
                
                if active:
                    logger.info(f"\n  Selected Templates:")
                    for template_id in active:
                        # Find template name
                        template = next((t for t in AVAILABLE_TEMPLATES if t["id"] == template_id), None)
                        if template:
                            logger.info(f"    ✓ {template_id}: {template['name']}")
                        else:
                            logger.warning(f"    ⚠️  {template_id}: UNKNOWN TEMPLATE")
                    
                    # Check for specific templates
                    has_outside = "outside-cleaning" in active
                    has_carpet = "carpet-cleaning" in active
                    
                    logger.info(f"\n  Specific Templates:")
                    logger.info(f"    - Outside Cleaning: {'✓ YES' if has_outside else '✗ NO'}")
                    logger.info(f"    - Carpet Cleaning: {'✓ YES' if has_carpet else '✗ NO'}")
                    
                    # Check for invalid IDs
                    invalid = [tid for tid in active if tid not in available_ids]
                    if invalid:
                        logger.warning(f"\n  ⚠️  Invalid Template IDs: {invalid}")
                else:
                    logger.warning(f"\n  ⚠️  No templates selected (empty array)")
                    logger.info(f"  💡 This means ALL templates will be shown to clients (backward compatibility)")
            else:
                logger.error(f"\n❌ No Business Config Found")
                logger.info(f"  💡 User has not completed onboarding")
            
            logger.info(f"{'='*80}\n")
    
    finally:
        db.close()

def main():
    """Main entry point"""
    email = sys.argv[1] if len(sys.argv) > 1 else None
    
    if email:
        logger.info(f"🔍 Verifying templates for: {email}")
    else:
        logger.info(f"🔍 Verifying templates for ALL users")
    
    verify_templates(email)

if __name__ == "__main__":
    main()
