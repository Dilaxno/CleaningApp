#!/usr/bin/env python3
"""
Smarty API Setup Script

This script helps you securely configure Smarty API credentials for address autocomplete.
Run this script to validate your API keys and set up the environment.
"""

import os
import sys
from pathlib import Path

try:
    import httpx
    import asyncio
except ImportError:
    print("❌ Missing dependencies. Please install httpx:")
    print("   pip install httpx")
    sys.exit(1)


def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found. Please create one based on .env.example")
        return False
    
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value
    return True


async def test_smarty_api(auth_id: str, auth_token: str):
    """Test Smarty API credentials"""
    url = "https://us-autocomplete-pro.api.smarty.com/lookup"
    params = {
        "auth-id": auth_id,
        "auth-token": auth_token,
        "search": "1 E Main St",
        "max_results": "1",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", [])
                print(f"✅ API test successful! Found {len(suggestions)} suggestions")
                if suggestions:
                    print(f"   Sample: {suggestions[0].get('text', 'N/A')}")
                return True
            elif response.status_code == 401:
                print("❌ Authentication failed. Please check your Auth ID and Auth Token")
                return False
            elif response.status_code == 402:
                print("❌ Payment required. Please check your Smarty account billing")
                return False
            else:
                print(f"❌ API error: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def main():
    print("🏠 Smarty Address Autocomplete Setup")
    print("=" * 40)
    
    # Load environment variables
    if not load_env_file():
        return
    
    # Get API credentials
    auth_id = os.getenv("SMARTY_AUTH_ID")
    auth_token = os.getenv("SMARTY_AUTH_TOKEN")
    
    if not auth_id or not auth_token:
        print("❌ Smarty API credentials not found in .env file")
        print("\nPlease add the following to your .env file:")
        print("SMARTY_AUTH_ID=your-smarty-auth-id")
        print("SMARTY_AUTH_TOKEN=your-smarty-auth-token")
        print("\nGet your credentials from: https://www.smarty.com/")
        return
    
    print(f"📋 Auth ID: {auth_id}")
    print(f"🔑 Auth Token: {'*' * (len(auth_token) - 4) + auth_token[-4:]}")
    print()
    
    # Test API connection
    print("🧪 Testing API connection...")
    success = asyncio.run(test_smarty_api(auth_id, auth_token))
    
    if success:
        print("\n✅ Smarty API is configured correctly!")
        print("\n📝 Next steps:")
        print("1. Restart your backend server")
        print("2. Test address autocomplete in your application")
        print("3. Monitor usage in your Smarty dashboard")
    else:
        print("\n❌ Setup incomplete. Please fix the issues above.")
        print("\n🔗 Helpful links:")
        print("- Smarty Dashboard: https://www.smarty.com/dashboard")
        print("- API Documentation: https://www.smarty.com/docs/cloud/us-street-api")
        print("- Support: https://www.smarty.com/support")


if __name__ == "__main__":
    main()