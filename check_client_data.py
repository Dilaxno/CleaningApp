"""
Check client data to diagnose frequency issue
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Client
from app import models_invoice  # noqa: F401
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_clients():
    """Check all clients and their frequency data"""
    db = SessionLocal()
    try:
        # Get all clients
        clients = db.query(Client).all()
        
        logger.info(f"Total clients: {len(clients)}")
        logger.info("=" * 80)
        
        for client in clients:
            logger.info(f"\nClient ID: {client.id}")
            logger.info(f"  Business Name: {client.business_name}")
            logger.info(f"  Status: {client.status}")
            logger.info(f"  Frequency (column): {client.frequency}")
            logger.info(f"  Property Type: {client.property_type}")
            logger.info(f"  Has form_data: {client.form_data is not None}")
            
            if client.form_data:
                logger.info(f"  form_data keys: {list(client.form_data.keys())}")
                cleaning_freq = client.form_data.get("cleaningFrequency")
                logger.info(f"  cleaningFrequency in form_data: {cleaning_freq}")
                
                # Check for other possible frequency keys
                for key in client.form_data.keys():
                    if 'freq' in key.lower() or 'schedule' in key.lower():
                        logger.info(f"  Found related key '{key}': {client.form_data[key]}")
                
                if not client.frequency and cleaning_freq:
                    logger.warning(f"  ⚠️ MISSING: Frequency column is empty but form_data has: {cleaning_freq}")
            
            logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Checking client data...")
    check_clients()
    logger.info("\nCheck complete!")
