#!/usr/bin/env python3
"""
Debug script to decode Firebase tokens and see their claims
Usage: python debug_token.py <token>
"""

import sys
import json
import base64

def decode_jwt_payload(token):
    """Decode JWT payload without verification (for debugging only)"""
    try:
        # Split token into parts
        parts = token.split('.')
        if len(parts) != 3:
            print(f"❌ Invalid token format: {len(parts)} parts (expected 3)")
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Decode header
        header_padding = 4 - len(header_b64) % 4
        if header_padding != 4:
            header_b64_padded = header_b64 + '=' * header_padding
        else:
            header_b64_padded = header_b64
        
        header = json.loads(base64.urlsafe_b64decode(header_b64_padded))
        
        # Decode payload
        payload_padding = 4 - len(payload_b64) % 4
        if payload_padding != 4:
            payload_b64_padded = payload_b64 + '=' * payload_padding
        else:
            payload_b64_padded = payload_b64
        
        payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded))
        
        print("🔍 JWT Token Analysis")
        print("=" * 50)
        print(f"📋 Header: {json.dumps(header, indent=2)}")
        print(f"📋 Payload: {json.dumps(payload, indent=2)}")
        print("=" * 50)
        
        # Check for user ID claims
        user_id_claims = ['sub', 'uid', 'user_id']
        print("🆔 User ID Claims:")
        for claim in user_id_claims:
            value = payload.get(claim)
            if value:
                print(f"  ✅ {claim}: {value}")
            else:
                print(f"  ❌ {claim}: Not found")
        
        print(f"\n📧 Email: {payload.get('email', 'Not found')}")
        print(f"👤 Name: {payload.get('name', 'Not found')}")
        print(f"🏢 Issuer: {payload.get('iss', 'Not found')}")
        print(f"🎯 Audience: {payload.get('aud', 'Not found')}")
        
        return payload
        
    except Exception as e:
        print(f"❌ Failed to decode token: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_token.py <firebase_token>")
        sys.exit(1)
    
    token = sys.argv[1]
    decode_jwt_payload(token)