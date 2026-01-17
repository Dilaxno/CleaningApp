#!/usr/bin/env python3
"""
Optional cleanup script to remove old dynamic products from Dodo Payments
Run this after switching to the adhoc product approach
"""
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models_invoice import Invoice
from app.config import DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT, DODO_ADHOC_PRODUCT_ID

async def cleanup_old_products():
    """Clean up old dynamic products and update invoices to use adhoc product"""
    
    if not DODO_PAYMENTS_API_KEY:
        print("❌ DODO_PAYMENTS_API_KEY not configured")
        return
    
    try:
        from dodopayments import AsyncDodoPayments
        
        dodo_client = AsyncDodoPayments(
            bearer_token=DODO_PAYMENTS_API_KEY,
            environment=DODO_PAYMENTS_ENVIRONMENT or "test_mode",
        )
        
        # Get database session
        db = next(get_db())
        
        # Find all invoices with dynamic product IDs (not the adhoc one)
        invoices_with_products = db.query(Invoice).filter(
            Invoice.dodo_product_id.isnot(None),
            Invoice.dodo_product_id != DODO_ADHOC_PRODUCT_ID
        ).all()
        
        print(f"Found {len(invoices_with_products)} invoices with old dynamic products")
        
        deleted_count = 0
        updated_count = 0
        
        for invoice in invoices_with_products:
            try:
                # Try to delete the old product (if it exists)
                if invoice.dodo_product_id and invoice.dodo_product_id != DODO_ADHOC_PRODUCT_ID:
                    try:
                        await dodo_client.products.delete(invoice.dodo_product_id)
                        deleted_count += 1
                        print(f"✅ Deleted product {invoice.dodo_product_id} for invoice {invoice.invoice_number}")
                    except Exception as e:
                        print(f"⚠️ Could not delete product {invoice.dodo_product_id}: {e}")
                
                # Update invoice to use adhoc product
                invoice.dodo_product_id = DODO_ADHOC_PRODUCT_ID
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error processing invoice {invoice.id}: {e}")
        
        # Commit all updates
        db.commit()
        db.close()
        
        print(f"\n✅ Cleanup completed:")
        print(f"   - Deleted {deleted_count} old products")
        print(f"   - Updated {updated_count} invoices to use adhoc product")
        print(f"   - Adhoc product ID: {DODO_ADHOC_PRODUCT_ID}")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    print("🧹 Starting Dodo Products cleanup...")
    print(f"Using adhoc product: {DODO_ADHOC_PRODUCT_ID}")
    
    # Confirm before proceeding
    response = input("This will delete old dynamic products. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Cleanup cancelled")
        sys.exit(0)
    
    asyncio.run(cleanup_old_products())