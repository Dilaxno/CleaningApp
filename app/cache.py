"""
Redis caching utilities for frequently accessed data
Reduces database load and improves response times
"""
import json
import logging
from typing import Optional, Any, Callable
from functools import wraps
from .rate_limiter import get_redis_client

logger = logging.getLogger(__name__)


class Cache:
    """Redis cache wrapper with automatic serialization"""
    
    def __init__(self):
        self.redis_client = None
    
    def _get_client(self):
        """Lazy load Redis client"""
        if self.redis_client is None:
            try:
                self.redis_client = get_redis_client()
            except Exception as e:
                logger.warning(f"⚠️ Redis cache unavailable: {e}")
                return None
        return self.redis_client
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        client = self._get_client()
        if not client:
            return None
        
        try:
            value = client.get(key)
            if value:
                logger.debug(f"✅ Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"❌ Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"❌ Cache get error for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL (default 1 hour)"""
        client = self._get_client()
        if not client:
            return False
        
        try:
            serialized = json.dumps(value)
            client.setex(key, ttl, serialized)
            logger.debug(f"✅ Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"❌ Cache set error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        client = self._get_client()
        if not client:
            return False
        
        try:
            client.delete(key)
            logger.debug(f"✅ Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Cache delete error for {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (e.g., 'user:123:*')"""
        client = self._get_client()
        if not client:
            return 0
        
        try:
            keys = client.keys(pattern)
            if keys:
                deleted = client.delete(*keys)
                logger.debug(f"✅ Cache DELETE pattern: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"❌ Cache delete pattern error for {pattern}: {e}")
            return 0


# Global cache instance
cache = Cache()


def cached(key_prefix: str, ttl: int = 3600, key_builder: Optional[Callable] = None):
    """
    Decorator to cache function results
    
    Args:
        key_prefix: Prefix for cache key (e.g., 'business_config')
        ttl: Time to live in seconds (default 1 hour)
        key_builder: Optional function to build cache key from function args
    
    Example:
        @cached(key_prefix='business_config', ttl=3600)
        def get_business_config(user_id: int):
            return db.query(BusinessConfig).filter(...).first()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use function name and first argument
                arg_str = str(args[0]) if args else "default"
                cache_key = f"{key_prefix}:{arg_str}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# Specific cache utilities for common use cases

def get_business_config_cached(user_id: int) -> Optional[dict]:
    """Get business config from cache"""
    return cache.get(f"business_config:{user_id}")


def set_business_config_cached(user_id: int, config: dict, ttl: int = 3600) -> bool:
    """Set business config in cache"""
    return cache.set(f"business_config:{user_id}", config, ttl)


def invalidate_business_config_cache(user_id: int) -> bool:
    """Invalidate business config cache when updated"""
    return cache.delete(f"business_config:{user_id}")


def get_user_plan_cached(user_id: int) -> Optional[dict]:
    """Get user plan info from cache"""
    return cache.get(f"user_plan:{user_id}")


def set_user_plan_cached(user_id: int, plan_data: dict, ttl: int = 300) -> bool:
    """Set user plan info in cache (5 minute TTL)"""
    return cache.set(f"user_plan:{user_id}", plan_data, ttl)


def invalidate_user_plan_cache(user_id: int) -> bool:
    """Invalidate user plan cache when plan changes"""
    return cache.delete(f"user_plan:{user_id}")


def invalidate_user_cache(user_id: int) -> int:
    """Invalidate all cache entries for a user"""
    pattern1_count = cache.delete_pattern(f"*:{user_id}:*")
    pattern2_count = cache.delete_pattern(f"*:{user_id}")
    return pattern1_count + pattern2_count


# Cache key builders for complex scenarios

def build_client_list_key(user_id: int, status: Optional[str] = None, skip: int = 0, limit: int = 50) -> str:
    """Build cache key for client list queries"""
    status_str = status or "all"
    return f"clients:{user_id}:{status_str}:{skip}:{limit}"


def build_contract_list_key(user_id: int, status: Optional[str] = None, skip: int = 0, limit: int = 50) -> str:
    """Build cache key for contract list queries"""
    status_str = status or "all"
    return f"contracts:{user_id}:{status_str}:{skip}:{limit}"


# Cache statistics (for monitoring)

def get_cache_stats() -> dict:
    """Get cache statistics"""
    client = cache._get_client()
    if not client:
        return {"available": False}
    
    try:
        info = client.info()
        return {
            "available": True,
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) / 
                max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
            ) * 100
        }
    except Exception as e:
        logger.error(f"❌ Failed to get cache stats: {e}")
        return {"available": False, "error": str(e)}
