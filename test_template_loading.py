#!/usr/bin/env python3
"""
Test script to verify template loading functionality
"""

import asyncio
import httpx
import json
import sys
from typing import Optional

API_URL = "http://localhost:8000"

async def test_template_endpoints(token: Optional[str] = None):
    """Test template-related endpoints"""
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing Template Endpoints")
        print("=" * 50)
        
        # Test 1: Get available templates (requires auth)
        if token:
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
                    print(f"Categories: {data.get('categories', [])}")
                else:
                    print(f"❌ Error: {response.text}")
            except Exception as e:
                print(f"❌ Exception: {e}")
        else:
            print("⏭️ Skipping authenticated endpoints (no token provided)")
        
        print()
        
        # Test 2: Get filtered templates for a specific user (public endpoint)
        try:
            print("📋 Testing /template-selection/filtered/{owner_uid}...")
            # Use a test Firebase UID - this should fail gracefully
            test_uid = "test-firebase-uid-123"
            response = await client.get(
                f"{API_URL}/template-selection/filtered/{test_uid}",
                timeout=10.0
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 404:
                print("✅ Correctly returned 404 for non-existent user")
            elif response.status_code == 200:
                data = response.json()
                print(f"✅ Found {len(data.get('templates', []))} filtered templates")
            else:
                print(f"❌ Unexpected response: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()
        
        # Test 3: Check if server is responding
        try:
            print("🏥 Testing server health...")
            response = await client.get(f"{API_URL}/", timeout=5.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("✅ Server is responding")
            else:
                print(f"⚠️ Server returned: {response.status_code}")
        except Exception as e:
            print(f"❌ Server connection failed: {e}")

if __name__ == "__main__":
    token = None
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print(f"🔑 Using provided token (length: {len(token)})")
    else:
        print("💡 Usage: python test_template_loading.py [firebase_token]")
        print("💡 Running without token (only public endpoints will be tested)")
    
    asyncio.run(test_template_endpoints(token))