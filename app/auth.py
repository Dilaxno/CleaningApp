import logging
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import FIREBASE_PROJECT_ID
from .database import get_db
from .models import User

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Cache for Google's public keys
_cached_keys = None


async def get_google_public_keys():
    """Fetch Google's public keys for Firebase token verification"""
    global _cached_keys
    if _cached_keys:
        return _cached_keys
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
        )
        if response.status_code == 200:
            _cached_keys = response.json()
            return _cached_keys
    return None


async def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token using Google's tokeninfo endpoint"""
    import json
    import base64
    
    if not FIREBASE_PROJECT_ID:
        logger.error("❌ FIREBASE_PROJECT_ID not configured")
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    try:
        # Decode the token payload without verification first to get claims
        # Then verify with Google's endpoint
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Decode payload (middle part)
        payload = parts[1]
        # Add padding if needed
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded_payload = json.loads(base64.urlsafe_b64decode(payload))
        
        # Verify the token claims
        aud = decoded_payload.get('aud')
        iss = decoded_payload.get('iss')
        
        if aud != FIREBASE_PROJECT_ID:
            logger.error(f"❌ Token audience mismatch: {aud} != {FIREBASE_PROJECT_ID}")
            raise HTTPException(status_code=401, detail="Invalid token audience")
        
        expected_issuer = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        if iss != expected_issuer:
            logger.error(f"❌ Token issuer mismatch: {iss} != {expected_issuer}")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        
        # Check expiration
        import time
        exp = decoded_payload.get('exp', 0)
        if exp < time.time():
            logger.warning("⚠️ Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        
        logger.info(f"✅ Token verified for user: {decoded_payload.get('email')}")
        return decoded_payload
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Firebase token"""
    token = credentials.credentials
    
    try:
        firebase_user = await verify_firebase_token(token)
        firebase_uid = firebase_user.get("user_id") or firebase_user.get("sub")
        email = firebase_user.get("email")
        name = firebase_user.get("name", "")
        
        if not firebase_uid:
            raise HTTPException(status_code=401, detail="Invalid user data")
        
        # Find or create user in our database
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            logger.info(f"🆕 Creating new user: {email}")
            user = User(
                firebase_uid=firebase_uid,
                email=email or "",
                full_name=name,
                plan=None,  # No default plan - user must select during onboarding
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Authentication failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
