#!/usr/bin/env python3
"""
One-time script to synchronize onboarding status between User and BusinessConfig tables.
This fixes any existing inconsistencies that may have caused users to lose onboarding progress.

Run this after deploying the backend fixes to ensure all existing users have consistent data.
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path so we can import models
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Import all models to avoid circular dependency issues
from app.models import User, BusinessConfig
from app.models_invoice import Invoice  # Import Invoice model to resolve dependencies
from app.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_onboarding_status():
    """Synchronize onboarding status between User and BusinessConfig tables"""
    
    # Create database connection
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Find all users
        users = db.query(User).all()
        logger.info(f"🔍 Found {len(users)} users to check")
        
        synced_count = 0
        issues_fixed = 0
        
        for user in users:
            # Get user's business config
            config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
            
            user_onboarding = user.onboarding_completed or False
            config_onboarding = config.onboarding_complete if config else False
            
            # Check if they're out of sync
            if user_onboarding != config_onboarding:
                logger.info(f"🔄 User {user.id} ({user.email}): User={user_onboarding}, Config={config_onboarding}")
                
                # Use OR logic - if either is True, set both to True
                should_be_complete = user_onboarding or config_onboarding
                
                # Update User table
                if user.onboarding_completed != should_be_complete:
                    user.onboarding_completed = should_be_complete
                    logger.info(f"   ✅ Updated User.onboarding_completed to {should_be_complete}")
                
                # Update BusinessConfig table if it exists
                if config and config.onboarding_complete != should_be_complete:
                    config.onboarding_complete = should_be_complete
                    logger.info(f"   ✅ Updated BusinessConfig.onboarding_complete to {should_be_complete}")
                
                issues_fixed += 1
            
            synced_count += 1
            
            if synced_count % 100 == 0:
                logger.info(f"📊 Processed {synced_count}/{len(users)} users...")
        
        # Commit all changes
        db.commit()
        
        logger.info(f"✅ Synchronization complete!")
        logger.info(f"   📊 Total users processed: {synced_count}")
        logger.info(f"   🔧 Issues fixed: {issues_fixed}")
        
        if issues_fixed > 0:
            logger.info(f"   🎉 Fixed onboarding status for {issues_fixed} users")
        else:
            logger.info(f"   ✨ All users already had consistent onboarding status")
            
    except Exception as e:
        logger.error(f"❌ Error during synchronization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("🚀 Starting onboarding status synchronization...")
    sync_onboarding_status()
    logger.info("🏁 Synchronization script completed")