"""
Hybrid in-memory + Redis rate limiting utilities
Optimized to minimize Redis commands and stay within Upstash limits
"""

import logging
import os
import time
from threading import Lock
from typing import Optional

import redis
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

# Redis connection
redis_client: Optional[redis.Redis] = None

# In-memory cache for rate limiting (dramatically reduces Redis usage)
# Format: {key: {'count': int, 'reset_time': int, 'last_redis_sync': int}}
memory_cache: dict[str, dict] = {}
cache_lock = Lock()

# Configuration
MEMORY_CACHE_SYNC_INTERVAL = 10  # Sync to Redis every 10 seconds
MEMORY_CACHE_CLEANUP_INTERVAL = 60  # Clean up expired entries every 60 seconds
last_cleanup_time = 0


def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client
    Supports both standard Redis and Upstash managed Redis
    """
    global redis_client

    if redis_client is None:
        logger.info("🔄 Initializing Redis connection for rate limiting...")

        # Check if using Upstash Redis URL (preferred method)
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            # Mask password in URL for logging
            if "@" in redis_url:
                url_parts = redis_url.split("@")
                protocol = url_parts[0].split(":")[0]
                masked_url = f"{protocol}:****@{url_parts[1]}"
            else:
                masked_url = "****"
            logger.info(f"📡 Using Redis URL connection: {masked_url}")

            # Use Redis URL (Upstash or other managed Redis)
            try:
                redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=15,  # Increased from 5 seconds
                    socket_timeout=30,  # Increased from 5 seconds
                    retry_on_timeout=True,  # Retry on timeout
                    health_check_interval=30,  # Health check every 30 seconds
                    max_connections=20,  # Connection pooling
                )
                # Test connection
                redis_client.ping()
                logger.info("Redis connected successfully via URL")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis via URL: {str(e)}")
                logger.error(
                    "⚠️ Rate limiting will NOT work - all requests will be allowed (fail-open mode)"
                )
                raise
        else:
            # Use individual Redis configuration (self-hosted or Upstash)
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD", None)
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

            logger.info("📡 Using individual Redis configuration:")
            logger.info(f"   Host: {redis_host}")
            logger.info(f"   Port: {redis_port}")
            logger.info(f"   Database: {redis_db}")
            logger.info(f"   SSL: {'Enabled' if redis_ssl else 'Disabled'}")
            logger.info(f"   Password: {'Set' if redis_password else 'Not set'}")

            try:
                redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    ssl=redis_ssl,
                    decode_responses=True,
                    socket_connect_timeout=15,  # Increased from 5 seconds
                    socket_timeout=30,  # Increased from 5 seconds
                    retry_on_timeout=True,  # Retry on timeout
                    health_check_interval=30,  # Health check every 30 seconds
                    max_connections=20,  # Connection pooling
                )
                # Test connection
                redis_client.ping()
                ssl_status = "with SSL" if redis_ssl else "without SSL"
                logger.info(
                    f"Redis connected successfully at {redis_host}:{redis_port} ({ssl_status})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis: {str(e)}")
                logger.error(
                    "⚠️ Rate limiting will NOT work - all requests will be allowed (fail-open mode)"
                )
                raise

    return redis_client


def cleanup_expired_cache():
    """Remove expired entries from memory cache"""
    global last_cleanup_time
    current_time = int(time.time())

    if current_time - last_cleanup_time < MEMORY_CACHE_CLEANUP_INTERVAL:
        return

    with cache_lock:
        expired_keys = [
            k for k, v in memory_cache.items() if current_time >= v.get("reset_time", 0)
        ]
        for k in expired_keys:
            del memory_cache[k]

        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired rate limit entries")

    last_cleanup_time = current_time


def check_rate_limit(
    key: str, limit: int, window_seconds: int, redis_client: redis.Redis
) -> tuple[bool, int, int]:
    """Check if rate limit is exceeded using hybrid in-memory + Redis approach

    This dramatically reduces Redis usage by:
    1. Checking in-memory cache first (no Redis calls)
    2. Only syncing to Redis every 10 seconds
    3. Using simple INCR instead of sorted sets (1 command vs 6-7)

    Args:
        key: Redis key for this rate limit
        limit: Maximum number of requests allowed
        window_seconds: Time window in seconds
        redis_client: Redis client instance

    Returns:
        Tuple of (is_allowed, current_count, ttl_seconds)
    """
    try:
        current_time = int(time.time())

        # Periodic cleanup of expired cache
        cleanup_expired_cache()

        with cache_lock:
            # Get or create cache entry
            if key not in memory_cache:
                # Initialize from Redis if exists, otherwise create new
                try:
                    redis_count = redis_client.get(key)
                    redis_ttl = redis_client.ttl(key)

                    if redis_count and redis_ttl > 0:
                        memory_cache[key] = {
                            "count": int(redis_count),
                            "reset_time": current_time + redis_ttl,
                            "last_redis_sync": current_time,
                        }
                    else:
                        # New window
                        memory_cache[key] = {
                            "count": 0,
                            "reset_time": current_time + window_seconds,
                            "last_redis_sync": current_time,
                        }
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load from Redis, using memory only: {e}")
                    memory_cache[key] = {
                        "count": 0,
                        "reset_time": current_time + window_seconds,
                        "last_redis_sync": current_time,
                    }

            cache_entry = memory_cache[key]

            # Check if window has expired
            if current_time >= cache_entry["reset_time"]:
                # Reset window
                cache_entry["count"] = 0
                cache_entry["reset_time"] = current_time + window_seconds
                cache_entry["last_redis_sync"] = 0

            # Check limit
            current_count = cache_entry["count"]
            is_allowed = current_count < limit

            if is_allowed:
                cache_entry["count"] += 1

            # Sync to Redis periodically (not on every request!)
            time_since_sync = current_time - cache_entry.get("last_redis_sync", 0)
            if time_since_sync >= MEMORY_CACHE_SYNC_INTERVAL:
                try:
                    # Use simple INCR + EXPIRE (only 2 Redis commands!)
                    pipe = redis_client.pipeline()
                    pipe.set(key, cache_entry["count"], ex=window_seconds)
                    pipe.execute()
                    cache_entry["last_redis_sync"] = current_time
                    logger.debug(f"📡 Synced {key} to Redis: {cache_entry['count']}/{limit}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to sync to Redis: {e}")

            ttl = cache_entry["reset_time"] - current_time
            return is_allowed, cache_entry["count"], max(0, ttl)

    except Exception as e:
        logger.error(f"❌ Rate limit check failed: {str(e)}")
        # Fail closed for security - deny request if rate limiting fails
        logger.warning("🔒 Denying request due to rate limiting error (fail-closed mode)")
        return False, limit, 0


async def rate_limit_dependency(
    request: Request,
    limit: int,
    window_seconds: int,
    key_prefix: str = "rate_limit",
    use_ip: bool = True,
):
    """
    FastAPI dependency for rate limiting

    Args:
        request: FastAPI request object
        limit: Maximum requests allowed
        window_seconds: Time window in seconds
        key_prefix: Prefix for Redis key
        use_ip: If True, use client IP in key (per-IP limit), otherwise global
    """
    try:
        client = get_redis_client()

        # Build rate limit key
        if use_ip:
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

            key = f"{key_prefix}:{client_ip}"
            logger.debug(f"🔍 Rate limit check for {key_prefix} - IP: {client_ip}")
        else:
            key = f"{key_prefix}:global"
            logger.debug(f"🔍 Rate limit check for {key_prefix} - Global")

        is_allowed, current_count, ttl = check_rate_limit(key, limit, window_seconds, client)

        if not is_allowed:
            retry_after = ttl
            logger.warning(
                f"🚫 Rate limit EXCEEDED for {key} - {current_count}/{limit} requests used"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds.",
                    "retry_after": retry_after,
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
                headers={"Retry-After": str(retry_after)},
            )

        if current_count % 100 == 0:
            logger.debug(f"Rate limit status for {key} - {current_count}/{limit} requests used")

        # Add rate limit headers to response (will be added by middleware if needed)
        request.state.rate_limit_remaining = limit - current_count
        request.state.rate_limit_limit = limit
        request.state.rate_limit_reset = int(time.time()) + ttl

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rate limiting error: {str(e)}")
        logger.warning("🔒 Denying request due to rate limiting error (fail-closed mode)")
        # Fail closed for security - deny request if rate limiting fails
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service temporarily unavailable",
        ) from e


def create_rate_limiter(
    limit: int, window_seconds: int, key_prefix: str = "rate_limit", use_ip: bool = True
):
    """
    Create a rate limiter dependency with specific parameters

    Example usage:
        rate_limit_5_per_hour = create_rate_limiter(limit=5, window_seconds=3600, key_prefix="password_reset")

        @router.post("/reset-password")
        async def reset_password(
            data: ResetPasswordRequest,
            _: None = Depends(rate_limit_5_per_hour)
        ):
            ...
    """

    async def rate_limiter(request: Request):
        return await rate_limit_dependency(request, limit, window_seconds, key_prefix, use_ip)

    return rate_limiter
