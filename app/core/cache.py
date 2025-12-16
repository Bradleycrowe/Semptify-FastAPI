"""
Redis Caching Utilities for Semptify.

Provides a simple caching layer with Redis backend (production)
and in-memory fallback (development).

Usage:
    from app.core.cache import cache
    
    # Simple get/set
    await cache.set("key", {"data": "value"}, ttl=300)
    data = await cache.get("key")
    
    # Decorator for function caching
    @cached(ttl=60, key_prefix="user")
    async def get_user(user_id: str):
        return await db.fetch_user(user_id)
    
    # Cache invalidation
    await cache.delete("key")
    await cache.clear_prefix("user:")
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class InMemoryCache:
    """Simple in-memory cache for development/testing."""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime | None]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                return None
            
            value, expires_at = self._cache[key]
            
            # Check expiration
            if expires_at and datetime.utcnow() > expires_at:
                del self._cache[key]
                return None
            
            return value
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache with optional TTL (seconds)."""
        async with self._lock:
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self._cache[key] = (value, expires_at)
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return await self.get(key) is not None
    
    async def clear_prefix(self, prefix: str) -> int:
        """Delete all keys with given prefix."""
        async with self._lock:
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    async def clear_all(self) -> None:
        """Clear entire cache."""
        async with self._lock:
            self._cache.clear()
    
    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            now = datetime.utcnow()
            valid_count = 0
            expired_count = 0
            
            for _, (_, expires_at) in self._cache.items():
                if expires_at is None or now <= expires_at:
                    valid_count += 1
                else:
                    expired_count += 1
            
            return {
                "backend": "memory",
                "total_keys": len(self._cache),
                "valid_keys": valid_count,
                "expired_keys": expired_count,
            }


class RedisCache:
    """Redis-backed cache for production."""
    
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None
        self._connected = False
    
    async def _ensure_connected(self) -> bool:
        """Ensure Redis connection is established."""
        if self._connected and self._redis:
            return True
        
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info("Redis cache connected: %s", self._redis_url.split("@")[-1])
            return True
        except ImportError:
            logger.warning("redis package not installed, falling back to memory cache")
            return False
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            return False
    
    async def get(self, key: str) -> Any | None:
        """Get value from Redis."""
        if not await self._ensure_connected():
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Redis GET error: %s", e)
            return None
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in Redis with optional TTL."""
        if not await self._ensure_connected():
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error("Redis SET error: %s", e)
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not await self._ensure_connected():
            return False
        
        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error("Redis DELETE error: %s", e)
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not await self._ensure_connected():
            return False
        
        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error("Redis EXISTS error: %s", e)
            return False
    
    async def clear_prefix(self, prefix: str) -> int:
        """Delete all keys with given prefix."""
        if not await self._ensure_connected():
            return 0
        
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    deleted += await self._redis.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.error("Redis CLEAR_PREFIX error: %s", e)
            return 0
    
    async def clear_all(self) -> None:
        """Clear entire cache (use with caution)."""
        if not await self._ensure_connected():
            return
        
        try:
            await self._redis.flushdb()
        except Exception as e:
            logger.error("Redis FLUSHDB error: %s", e)
    
    async def get_stats(self) -> dict[str, Any]:
        """Get Redis statistics."""
        if not await self._ensure_connected():
            return {"backend": "redis", "connected": False}
        
        try:
            info = await self._redis.info("memory")
            return {
                "backend": "redis",
                "connected": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            return {"backend": "redis", "connected": False, "error": str(e)}


class CacheManager:
    """
    Unified cache manager with automatic backend selection.
    Uses Redis if available, falls back to in-memory cache.
    """
    
    def __init__(self):
        self._backend: InMemoryCache | RedisCache | None = None
        self._initialized = False
    
    async def _ensure_initialized(self) -> None:
        """Initialize cache backend based on settings."""
        if self._initialized:
            return
        
        from app.core.config import get_settings
        settings = get_settings()
        
        if settings.redis_url:
            redis_cache = RedisCache(settings.redis_url)
            if await redis_cache._ensure_connected():
                self._backend = redis_cache
                logger.info("Cache initialized with Redis backend")
            else:
                self._backend = InMemoryCache()
                logger.info("Cache initialized with in-memory backend (Redis unavailable)")
        else:
            self._backend = InMemoryCache()
            logger.info("Cache initialized with in-memory backend")
        
        self._initialized = True
    
    async def get(self, key: str) -> Any | None:
        """Get cached value."""
        await self._ensure_initialized()
        return await self._backend.get(key)
    
    async def set(self, key: str, value: Any, ttl: int | None = 300) -> bool:
        """Set cached value (default TTL: 5 minutes)."""
        await self._ensure_initialized()
        return await self._backend.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        await self._ensure_initialized()
        return await self._backend.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        await self._ensure_initialized()
        return await self._backend.exists(key)
    
    async def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with prefix."""
        await self._ensure_initialized()
        return await self._backend.clear_prefix(prefix)
    
    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        await self._ensure_initialized()
        return await self._backend.get_stats()


# Global cache instance
cache = CacheManager()


def _make_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
    return f"{prefix}:{key_hash}"


def cached(
    ttl: int = 300,
    key_prefix: str | None = None,
    key_builder: Callable[..., str] | None = None,
):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default: 300)
        key_prefix: Custom prefix for cache key (default: function name)
        key_builder: Custom function to build cache key
    
    Usage:
        @cached(ttl=60)
        async def get_user(user_id: str):
            return await db.fetch_user(user_id)
        
        # With custom key
        @cached(ttl=120, key_prefix="user_profile")
        async def get_profile(user_id: str, include_details: bool = False):
            return await fetch_profile(user_id, include_details)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        prefix = key_prefix or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _make_cache_key(prefix, args, kwargs)
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache HIT: %s", cache_key)
                return cached_value
            
            # Execute function and cache result
            logger.debug("Cache MISS: %s", cache_key)
            result = await func(*args, **kwargs)
            
            if result is not None:
                await cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: cache.clear_prefix(f"{prefix}:")
        wrapper.cache_key = lambda *a, **kw: _make_cache_key(prefix, a, kw)
        
        return wrapper
    
    return decorator


def cache_invalidate(key_prefix: str):
    """
    Decorator to invalidate cache after function execution.
    
    Usage:
        @cache_invalidate("user")
        async def update_user(user_id: str, data: dict):
            return await db.update_user(user_id, data)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)
            
            # Invalidate cache after successful execution
            deleted = await cache.clear_prefix(f"{key_prefix}:")
            if deleted:
                logger.debug("Cache invalidated: %s (%d keys)", key_prefix, deleted)
            
            return result
        
        return wrapper
    
    return decorator
