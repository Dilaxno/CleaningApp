import json
import logging

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from .config import FIREBASE_PROJECT_ID
from .database import get_db
from .models import User
from .security_middleware import set_rls_context

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Cache for Google's public keys
_cached_keys = None


async def get_google_public_keys():
    """Fetch Google's public keys for Firebase token verification"""
    global _cached_keys
    if _cached_keys:
        logger.debug("✅ Using cached Google public keys")
        return _cached_keys

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
            )
            if response.status_code == 200:
                _cached_keys = response.json()
                logger.info(f"✅ Fetched {len(_cached_keys)} Google public keys")
                return _cached_keys
            else:
                logger.error(f"❌ Failed to fetch Google public keys: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error fetching Google public keys: {str(e)}")
    return None


async def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token with FULL cryptographic signature verification.
    Uses Google's public keys to verify the JWT signature.
    """
    import base64
    import json
    import time

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.x509 import load_pem_x509_certificate

    if not FIREBASE_PROJECT_ID:
        logger.error("❌ FIREBASE_PROJECT_ID not configured")
        raise HTTPException(status_code=500, detail="Firebase not configured")

    try:
        # Split token into parts
        parts = token.split(".")
        if len(parts) != 3:
            logger.error("❌ Invalid token format: wrong number of parts")
            raise HTTPException(status_code=401, detail="Invalid token format")

        header_b64, payload_b64, signature_b64 = parts
        logger.debug("✅ Token split into 3 parts successfully")

        # Decode header to get key ID (kid)
        header_padding = 4 - len(header_b64) % 4
        header_b64_padded = header_b64 + ("=" * header_padding if header_padding != 4 else "")

        try:
            header = json.loads(base64.urlsafe_b64decode(header_b64_padded))
            logger.debug("✅ Token header decoded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to decode token header: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token header") from e

        kid = header.get("kid")
        alg = header.get("alg")

        if alg != "RS256":
            logger.error(f"❌ Invalid token algorithm: {alg}")
            raise HTTPException(status_code=401, detail="Invalid token algorithm")

        if not kid:
            logger.error("❌ Token missing key ID")
            raise HTTPException(status_code=401, detail="Token missing key ID")

        logger.debug(f"✅ Token header validated: alg={alg}, kid={kid}")

        # Fetch Google's public keys
        public_keys = await get_google_public_keys()
        if not public_keys or kid not in public_keys:
            logger.warning(
                f"⚠️ Key ID {kid} not found in public keys, invalidating cache and retrying"
            )
            # Invalidate cache and retry
            global _cached_keys
            _cached_keys = None
            public_keys = await get_google_public_keys()
            if not public_keys or kid not in public_keys:
                logger.error(f"❌ Key ID {kid} not found in public keys after retry")
                raise HTTPException(status_code=401, detail="Unable to verify token signature")

        # Get the certificate for this key ID
        cert_pem = public_keys[kid]
        cert = load_pem_x509_certificate(cert_pem.encode(), default_backend())
        public_key = cert.public_key()
        logger.debug(f"✅ Public key loaded for kid: {kid}")

        # Decode signature
        sig_padding = 4 - len(signature_b64) % 4
        signature_b64_padded = signature_b64 + ("=" * sig_padding if sig_padding != 4 else "")

        try:
            signature = base64.urlsafe_b64decode(signature_b64_padded)
            logger.debug("✅ Token signature decoded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to decode token signature: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token signature format") from e

        # Verify signature (header.payload signed with private key)
        message = f"{header_b64}.{payload_b64}".encode()

        try:
            public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
            logger.debug("✅ Token signature verified successfully")
        except Exception as e:
            logger.error(f"❌ Token signature verification failed: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token signature") from e

        # Decode payload
        payload_padding = 4 - len(payload_b64) % 4
        payload_b64_padded = payload_b64 + ("=" * payload_padding if payload_padding != 4 else "")

        decoded_payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded))

        # Verify claims
        aud = decoded_payload.get("aud")
        iss = decoded_payload.get("iss")

        if aud != FIREBASE_PROJECT_ID:
            logger.error("❌ Token audience mismatch")
            raise HTTPException(status_code=401, detail="Invalid token audience")

        expected_issuer = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        if iss != expected_issuer:
            logger.error("❌ Token issuer mismatch")
            raise HTTPException(status_code=401, detail="Invalid token issuer")

        # Check expiration
        exp = decoded_payload.get("exp", 0)
        current_time = time.time()
        if exp < current_time:
            time_expired = int(current_time - exp)
            # Only log if significantly expired (> 60 seconds) to reduce noise
            if time_expired > 60:
                logger.info(
                    f"ℹ️ Token expired {time_expired}s ago for {decoded_payload.get('email')}"
                )
            raise HTTPException(
                status_code=401,
                detail="Token has expired. Please refresh your session.",
                headers={"X-Token-Expired": "true"},
            )

        # Check issued at time (iat) - token should not be from the future
        iat = decoded_payload.get("iat", 0)
        if iat > time.time() + 60:  # Allow 60 seconds clock skew
            logger.warning("⚠️ Token issued in the future")
            raise HTTPException(status_code=401, detail="Invalid token")

        # Check auth_time exists
        if "auth_time" not in decoded_payload:
            raise HTTPException(status_code=401, detail="Invalid token claims")

        logger.debug(
            f"✅ Token cryptographically verified for user: {decoded_payload.get('email')}"
        )
        return decoded_payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token verification failed: {str(e)}")
        logger.error(f"❌ Token verification error details: {type(e).__name__}: {str(e)}")
        import traceback

        logger.error(f"❌ Token verification traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail="Token verification failed") from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current user from Firebase token"""

    if not credentials:
        logger.error("❌ No credentials provided")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please provide a valid Bearer token in the Authorization header.",
        )

    token = credentials.credentials
    logger.info(f"🔍 Authentication attempt - Token length: {len(token)}")

    # Basic token format validation before processing
    token_parts = token.split(".")
    if len(token_parts) != 3:
        # Log more details about malformed tokens for debugging
        logger.warning(
            f"⚠️ Malformed token received: {len(token_parts)} parts, token length: {len(token)}, first 20 chars: '{token[:20]}...'"
        )
        raise HTTPException(
            status_code=401, detail="Invalid token format. Expected a valid JWT token."
        )

    try:
        # Verify the Firebase token
        decoded_token = await verify_firebase_token(token)

        # Firebase ID tokens use 'sub' as the user ID claim, not 'uid'
        firebase_uid = (
            decoded_token.get("sub") or decoded_token.get("user_id") or decoded_token.get("uid")
        )
        email = decoded_token.get("email")
        name = decoded_token.get("name", "")

        if not firebase_uid:
            logger.error(
                f"❌ Token missing user ID claim. Available claims: {list(decoded_token.keys())}"
            )
            logger.error(
                f"❌ Token payload sample: {json.dumps({k: v for k, v in decoded_token.items() if k in ['sub', 'uid', 'user_id', 'email', 'iss', 'aud']}, indent=2)}"
            )
            raise HTTPException(status_code=401, detail="Invalid token claims")

        # Find or create user in our database
        user = (
            db.query(User)
            .filter(User.firebase_uid == firebase_uid)
            .options(joinedload(User.business_config))
            .first()
        )

        if not user:
            # Check if email is already registered with a different Firebase UID
            # This happens when user signs up with email/password then later uses Google auth
            if email:
                existing_user = db.query(User).filter(User.email == email).first()
                if existing_user:
                    logger.info(
                        f"🔄 Migrating user {email} from Firebase UID {existing_user.firebase_uid} to {firebase_uid}"
                    )
                    # Update the Firebase UID to the new one (e.g., Google auth UID)
                    existing_user.firebase_uid = firebase_uid
                    # Update name if provided and not already set
                    if name and not existing_user.full_name:
                        existing_user.full_name = name
                    try:
                        db.commit()
                        db.refresh(existing_user)
                        logger.info("✅ User migrated successfully to new Firebase UID")
                        return existing_user
                    except Exception as e:
                        db.rollback()
                        logger.error(f"❌ Failed to migrate user: {str(e)}")
                        raise HTTPException(
                            status_code=500, detail="Failed to update user authentication method"
                        ) from e

            # Create new user
            logger.info(f"🆕 Creating new user: {email}")
            user = User(
                firebase_uid=firebase_uid,
                email=email or "",
                full_name=name,
                plan=None,  # No default plan - user must select during onboarding
            )
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
                logger.info(f"✅ New user created: {user.email}")
            except Exception as e:
                db.rollback()
                # Handle race condition where email was taken between check and insert
                if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                    logger.error(f"❌ Email {email} was taken by another account (race condition)")
                    raise HTTPException(
                        status_code=409,
                        detail="This email is already registered. Please sign in with your existing account.",
                    ) from e
                raise

        logger.debug(f"✅ User authenticated: {user.email}")

        # Set RLS context for this database session
        set_rls_context(db, user.id)

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Authentication failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed") from e


async def get_current_user_with_plan(
    user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they have an active plan.
    Use this dependency for all dashboard routes that require a paid plan.
    """
    if not user.plan or user.plan.strip() == "":
        logger.warning(f"⚠️ User {user.email} attempted to access protected route without a plan")
        raise HTTPException(
            status_code=403,
            detail="Plan required. Please select a plan to access this feature.",
            headers={"X-Plan-Required": "true"},
        )

    logger.debug(f"✅ User {user.email} has plan: {user.plan}")
    return user
