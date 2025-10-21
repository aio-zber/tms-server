"""
Redis cache management.
Provides connection pooling and helper functions for caching operations.
"""
import json
from typing import Any, Optional
from redis import asyncio as aioredis
from app.config import settings


class RedisCache:
    """Redis cache manager with connection pooling."""

    def __init__(self):
        """Initialize Redis connection pool."""
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if not settings.redis_url:
            print("No Redis URL provided - running without Redis cache")
            self.redis = None
            return
            
        try:
            self.redis = await aioredis.from_url(
                settings.redis_url,
                password=settings.redis_password if settings.redis_password else None,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            # Test the connection
            await self.redis.ping()
            print("Connected to Redis successfully")
        except Exception as e:
            print(f"Warning: Could not connect to Redis: {e}")
            print("Running without Redis cache (development mode)")
            self.redis = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.redis:
            return None

        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        if ttl:
            return await self.redis.setex(key, ttl, value)
        else:
            return await self.redis.set(key, value)

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted
        """
        if not self.redis:
            return False

        return bool(await self.redis.delete(key))

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        if not self.redis:
            return False

        return bool(await self.redis.exists(key))

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment counter in cache.

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        if not self.redis:
            return 0

        return await self.redis.incrby(key, amount)

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            True if expiration was set
        """
        if not self.redis:
            return False

        return bool(await self.redis.expire(key, ttl))


# Global cache instance
cache = RedisCache()


# Helper functions for common cache patterns
async def cache_user_data(tms_user_id: str, user_data: dict) -> bool:
    """Cache user data from TMS."""
    key = f"user:{tms_user_id}"
    return await cache.set(key, user_data, ttl=settings.cache_user_ttl)


async def get_cached_user_data(tms_user_id: str) -> Optional[dict]:
    """Get cached user data."""
    key = f"user:{tms_user_id}"
    return await cache.get(key)


async def invalidate_user_cache(tms_user_id: str) -> bool:
    """Invalidate user cache."""
    key = f"user:{tms_user_id}"
    return await cache.delete(key)


async def set_user_presence(user_id: str, status: str) -> bool:
    """Set user presence status (online/offline/away)."""
    key = f"presence:{user_id}"
    return await cache.set(key, {"status": status}, ttl=settings.cache_presence_ttl)


async def get_user_presence(user_id: str) -> Optional[str]:
    """Get user presence status."""
    key = f"presence:{user_id}"
    data = await cache.get(key)
    return data.get("status") if data else None


# Unread count caching (Messenger/Telegram pattern)
async def cache_unread_count(user_id: str, conversation_id: str, count: int) -> bool:
    """
    Cache unread message count for a user in a conversation.

    Following Telegram/Messenger pattern with short TTL (60 seconds).
    Cache is invalidated when:
    - User marks messages as read
    - New message arrives in conversation
    - User opens conversation

    Args:
        user_id: User UUID string
        conversation_id: Conversation UUID string
        count: Number of unread messages

    Returns:
        True if cached successfully
    """
    key = f"unread:{user_id}:{conversation_id}"
    # Short TTL (60s) ensures fresh data while reducing DB load
    return await cache.set(key, count, ttl=60)


async def get_cached_unread_count(user_id: str, conversation_id: str) -> Optional[int]:
    """
    Get cached unread count for a user in a conversation.

    Args:
        user_id: User UUID string
        conversation_id: Conversation UUID string

    Returns:
        Cached count or None if cache miss
    """
    key = f"unread:{user_id}:{conversation_id}"
    count = await cache.get(key)
    return int(count) if count is not None else None


async def invalidate_unread_count_cache(user_id: str, conversation_id: str) -> bool:
    """
    Invalidate cached unread count (called when count changes).

    Args:
        user_id: User UUID string
        conversation_id: Conversation UUID string

    Returns:
        True if invalidated successfully
    """
    key = f"unread:{user_id}:{conversation_id}"
    return await cache.delete(key)


async def cache_total_unread_count(user_id: str, count: int) -> bool:
    """
    Cache total unread count across all conversations for a user.

    Args:
        user_id: User UUID string
        count: Total unread count

    Returns:
        True if cached successfully
    """
    key = f"unread:total:{user_id}"
    return await cache.set(key, count, ttl=60)


async def get_cached_total_unread_count(user_id: str) -> Optional[int]:
    """
    Get cached total unread count for a user.

    Args:
        user_id: User UUID string

    Returns:
        Cached total count or None if cache miss
    """
    key = f"unread:total:{user_id}"
    count = await cache.get(key)
    return int(count) if count is not None else None


async def invalidate_total_unread_count_cache(user_id: str) -> bool:
    """
    Invalidate cached total unread count.

    Args:
        user_id: User UUID string

    Returns:
        True if invalidated successfully
    """
    key = f"unread:total:{user_id}"
    return await cache.delete(key)
