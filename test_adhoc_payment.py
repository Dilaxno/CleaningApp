#!/usr/bin/env python3
"""
Test script to verify adhoc product payment link generation
"""
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT, DODO_ADHOC_PRODUCT_ID

async def test_adhoc_payment():
    """Test creating a checkout session with the adhoc product"""
    
    if not DODO_PAYMENTS_API_KEY:
        print("❌ DODO_PAYMENTS_API_KEY not configured")
        return
    
    if not DODO_ADHOC_PRODUCT_ID:
        print("❌ DODO_ADHOC_PRODUCT_ID not configured")
        return
    
    try:
        from dodopayments import AsyncDodoPayments
        
        dodo_client = AsyncDodoPayments(
            bearer_token=DODO_PAYMENTS_API_KEY,
            environment=DODO_PAYMENTS_ENVIRONMENT or "test_mode",
        )
        
        # Test creating a checkout session with custom amount
        test_amount = 150.00  # $150.00
        
        session_data = {
            "product_cart": [{
                "product_id": DODO_ADHOC_PRODUCT_ID,
                "quantity": 1,
                # Dynamic amount in lowest denomination (e.g., cents)
                "amount": int(round(test_amount * 100))
            }],
            "customer": {
                "email": "test@example.com",
                "name": "Test Client",
            },
            "metadata": {
                "invoice_id": "test_123",
                "invoice_number": "INV-TEST-001",
                "provider_user_id": "test_provider",
                "client_id": "test_client",
                "business_name": "Test Cleaning Service",
                "invoice_title": "Office Cleaning Service",
                "invoice_description": "Weekly office cleaning",
            },
            "return_url": "https://example.com/payment/success/test",
        }
        
        print(f"🧪 Testing checkout session creation...")
        print(f"   Adhoc Product ID: {DODO_ADHOC_PRODUCT_ID}")
        print(f"   Test Amount: ${test_amount}")
        print(f"   Environment: {DODO_PAYMENTS_ENVIRONMENT}")
        
        session = await dodo_client.checkout_sessions.create(**session_data)
        
        checkout_url = getattr(session, "checkout_url", None) or session.get("checkout_url")
        session_id = getattr(session, "session_id", None) or session.get("session_id")
        
        if checkout_url:
            print(f"✅ Checkout session created successfully!")
            print(f"   Session ID: {session_id}")
            print(f"   Checkout URL: {checkout_url}")
            print(f"\n🔗 Test the payment link:")
            print(f"   {checkout_url}")
        else:
            print("❌ Failed to get checkout URL from session")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Testing Dodo Adhoc Product Payment...")
    asyncio.run(test_adhoc_payment())