"""
Backfill client frequency from form_data
This script updates existing clients that have form_data but missing frequency field
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Client, User, Contract, Schedule
# Import Invoice model to ensure SQLAlchemy can resolve relationships
from app import models_invoice  # noqa: F401
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_frequency():
    """Update clients with missing frequency from their form_data or property_type"""
    db = SessionLocal()
    try:
        # Find clients with no frequency (NULL or empty string)
        clients = db.query(Client).filter(
            (Client.frequency.is_(None)) | (Client.frequency == "") | (Client.frequency == "None")
        ).all()
        
        logger.info(f"Found {len(clients)} clients with missing frequency")
        
        updated_count = 0
        for client in clients:
            frequency = None
            
            # Try to get from form_data first
            if client.form_data and isinstance(client.form_data, dict):
                frequency = client.form_data.get("cleaningFrequency")
            
            # If not in form_data, infer from property_type
            if not frequency and client.property_type:
                property_type_lower = client.property_type.lower()
                
                # Move-in/Move-out is always one-time
                if 'move' in property_type_lower:
                    frequency = "One-time"
                    logger.info(f"Inferred 'One-time' frequency for move-in-out client {client.id}")
                
                # Post-construction is typically one-time
                elif 'construction' in property_type_lower or 'post-construction' in property_type_lower:
                    frequency = "One-time"
                    logger.info(f"Inferred 'One-time' frequency for construction client {client.id}")
                
                # Event cleanup is one-time
                elif 'event' in property_type_lower:
                    frequency = "One-time"
                    logger.info(f"Inferred 'One-time' frequency for event client {client.id}")
            
            # Update if we found a frequency
            if frequency:
                client.frequency = frequency
                updated_count += 1
                logger.info(f"Updated client {client.id} ({client.business_name}) with frequency: {frequency}")
        
        db.commit()
        logger.info(f"✅ Successfully updated {updated_count} clients")
        
    except Exception as e:
        logger.error(f"❌ Error during backfill: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting frequency backfill...")
    backfill_frequency()
    logger.info("Backfill complete!")
