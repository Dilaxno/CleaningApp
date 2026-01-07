"""
Redis-based rate limiting utilities
"""
import redis
import os
import time
import logging
from typing import Optional
from fastapi import HTTPException, Request
from functools import wraps

logger = logging.getLogger(__name__)

# Redis connection
redis_client: Optional[redis.Redis] = None

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
            masked_url = redis_url.split('@')[0].split(':')[0] + ":****@" + redis_url.split('@')[1] if '@' in redis_url else "****"
            logger.info(f"📡 Using Redis URL connection: {masked_url}")
            
            # Use Redis URL (Upstash or other managed Redis)
            try:
                redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                info = redis_client.ping()
                logger.info(f"✅ Redis connected successfully via URL - Rate limiting is ACTIVE")
                logger.info(f"📊 Redis connection test: PONG received")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis via URL: {str(e)}")
                logger.error(f"⚠️ Rate limiting will NOT work - all requests will be allowed (fail-open mode)")
                raise
        else:
            # Use individual Redis configuration (self-hosted or Upstash)
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD", None)
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"
            
            logger.info(f"📡 Using individual Redis configuration:")
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
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                redis_client.ping()
                ssl_status = "with SSL" if redis_ssl else "without SSL"
                logger.info(f"✅ Redis connected successfully at {redis_host}:{redis_port} ({ssl_status})")
                logger.info(f"📊 Redis connection test: PONG received - Rate limiting is ACTIVE")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis: {str(e)}")
                logger.error(f"⚠️ Rate limiting will NOT work - all requests will be allowed (fail-open mode)")
                raise
    
    return redis_client


def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    redis_client: redis.Redis
) -> tuple[bool, int, int]:
    """
    Check if rate limit is exceeded using sliding window
    
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
        window_start = current_time - window_seconds
        
        # Use Redis sorted set with timestamps as scores
        pipe = redis_client.pipeline()
        
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiry on the key
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        current_count = results[1]
        
        # Check if limit exceeded (check before we added the current request)
        is_allowed = current_count < limit
        
        if not is_allowed:
            # Remove the request we just added since it's not allowed
            redis_client.zrem(key, str(current_time))
        
        ttl = redis_client.ttl(key)
        
        return is_allowed, current_count + 1, ttl if ttl > 0 else window_seconds
        
    except Exception as e:
        logger.error(f"❌ Rate limit check failed: {str(e)}")
        # Fail open - allow request if Redis is down
        return True, 0, 0


async def rate_limit_dependency(
    request: Request,
    limit: int,
    window_seconds: int,
    key_prefix: str = "rate_limit",
    use_ip: bool = True
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
            logger.warning(f"🚫 Rate limit EXCEEDED for {key} - {current_count}/{limit} requests used")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
        
        logger.debug(f"✅ Rate limit check passed for {key} - {current_count}/{limit} requests used")
        
        # Add rate limit headers to response (will be added by middleware if needed)
        request.state.rate_limit_remaining = limit - current_count
        request.state.rate_limit_limit = limit
        request.state.rate_limit_reset = int(time.time()) + ttl
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rate limiting error: {str(e)}")
        logger.warning(f"⚠️ Allowing request due to rate limiting error (fail-open mode)")
        # Fail open - allow request if rate limiting fails
        pass


def create_rate_limiter(limit: int, window_seconds: int, key_prefix: str = "rate_limit", use_ip: bool = True):
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
