"""
Session Storage Backend for Semptify.

Supports both in-memory storage (development) and Redis (production).
Sessions store authentication state for storage-based auth.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionBackend(ABC):
    """Abstract base class for session storage backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        """Get session data by key."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> bool:
        """Set session data with TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a session."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if session exists."""
        pass
    
    @abstractmethod
    async def extend(self, key: str, ttl_seconds: int = 3600) -> bool:
        """Extend session TTL."""
        pass


class MemorySessionBackend(SessionBackend):
    """
    In-memory session storage for development.
    NOT suitable for production (data lost on restart, no horizontal scaling).
    """
    
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._expiry: dict[str, datetime] = {}
    
    async def get(self, key: str) -> Optional[dict]:
        self._cleanup_expired()
        if key in self._store and key in self._expiry:
            if datetime.utcnow() < self._expiry[key]:
                return self._store[key]
            else:
                # Expired
                del self._store[key]
                del self._expiry[key]
        return None
    
    async def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> bool:
        self._store[key] = value
        self._expiry[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        return True
    
    async def delete(self, key: str) -> bool:
        deleted = key in self._store
        self._store.pop(key, None)
        self._expiry.pop(key, None)
        return deleted
    
    async def exists(self, key: str) -> bool:
        self._cleanup_expired()
        return key in self._store and key in self._expiry and datetime.utcnow() < self._expiry[key]
    
    async def extend(self, key: str, ttl_seconds: int = 3600) -> bool:
        if key in self._store:
            self._expiry[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            return True
        return False
    
    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = [k for k, exp in self._expiry.items() if now >= exp]
        for key in expired:
            self._store.pop(key, None)
            self._expiry.pop(key, None)


class RedisSessionBackend(SessionBackend):
    """
    Redis-backed session storage for production.
    Supports horizontal scaling and persistent sessions.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", prefix: str = "semptify:session:"):
        self.redis_url = redis_url
        self.prefix = prefix
        self._client = None
    
    async def _get_client(self):
        """Lazy-load Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
            except ImportError:
                logger.error("redis package not installed. Run: pip install redis")
                raise
        return self._client
    
    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}{key}"
    
    async def get(self, key: str) -> Optional[dict]:
        try:
            client = await self._get_client()
            data = await client.get(self._key(key))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error("Redis GET error: %s", e)
        return None
    
    async def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> bool:
        try:
            client = await self._get_client()
            data = json.dumps(value)
            await client.setex(self._key(key), ttl_seconds, data)
            return True
        except Exception as e:
            logger.error("Redis SET error: %s", e)
        return False
    
    async def delete(self, key: str) -> bool:
        try:
            client = await self._get_client()
            result = await client.delete(self._key(key))
            return result > 0
        except Exception as e:
            logger.error("Redis DELETE error: %s", e)
        return False
    
    async def exists(self, key: str) -> bool:
        try:
            client = await self._get_client()
            return await client.exists(self._key(key)) > 0
        except Exception as e:
            logger.error("Redis EXISTS error: %s", e)
        return False
    
    async def extend(self, key: str, ttl_seconds: int = 3600) -> bool:
        try:
            client = await self._get_client()
            return await client.expire(self._key(key), ttl_seconds)
        except Exception as e:
            logger.error("Redis EXPIRE error: %s", e)
        return False
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# =============================================================================
# Session Manager (Singleton)
# =============================================================================

_session_backend: Optional[SessionBackend] = None


def get_session_backend() -> SessionBackend:
    """Get the configured session backend."""
    global _session_backend
    if _session_backend is None:
        # Default to memory backend
        _session_backend = MemorySessionBackend()
        logger.info("Using in-memory session backend (development mode)")
    return _session_backend


def configure_session_backend(redis_url: Optional[str] = None):
    """
    Configure the session backend.
    
    Call this during application startup:
        configure_session_backend("redis://localhost:6379")
    
    Args:
        redis_url: Redis connection URL. If None, uses in-memory storage.
    """
    global _session_backend
    
    if redis_url:
        _session_backend = RedisSessionBackend(redis_url)
        logger.info("Using Redis session backend: %s", redis_url.split("@")[-1])  # Hide credentials
    else:
        _session_backend = MemorySessionBackend()
        logger.info("Using in-memory session backend (development mode)")


async def close_session_backend():
    """Close session backend connections (call during shutdown)."""
    global _session_backend
    if _session_backend and isinstance(_session_backend, RedisSessionBackend):
        await _session_backend.close()
    _session_backend = None
