#!/usr/bin/env python3
"""
Test script to debug authentication issues
"""

import asyncio
import httpx
import sys

API_URL = "https://api.cleanenroll.com"

async def test_auth_endpoints(token: str):
    """Test authentication endpoints"""
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing Authentication Endpoints")
        print("=" * 50)
        print(f"🔑 Token length: {len(token)}")
        print(f"🔑 Token preview: {token[:50]}...")
        print()
        
        # Test 1: Debug auth endpoint
        try:
            print("📋 Testing /template-selection/debug-auth...")
            response = await client.get(
                f"{API_URL}/template-selection/debug-auth",
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Authentication successful!")
                print(f"User ID: {data.get('user_id')}")
                print(f"Email: {data.get('email')}")
                print(f"Firebase UID: {data.get('firebase_uid')}")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # Test 2: Template selection endpoint
        try:
            print("📋 Testing /template-selection/available...")
            response = await client.get(
                f"{API_URL}/template-selection/available",
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {len(data.get('templates', []))} templates")
                print(f"✅ Found {len(data.get('categories', []))} categories")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # Test 3: Business config endpoint
        try:
            print("📋 Testing /business (business config)...")
            response = await client.get(
                f"{API_URL}/business",
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Business config loaded")
                print(f"Business name: {data.get('businessName', 'Not set')}")
                print(f"Onboarding complete: {data.get('onboardingComplete', False)}")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_auth_debug.py <firebase_token>")
        print("Get your Firebase token from browser dev tools:")
        print("1. Open browser dev tools (F12)")
        print("2. Go to Application/Storage tab")
        print("3. Look for Firebase auth token in localStorage or sessionStorage")
        print("4. Or check Network tab for Authorization header in API requests")
        sys.exit(1)
    
    token = sys.argv[1]
    asyncio.run(test_auth_endpoints(token))