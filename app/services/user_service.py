"""
User service for business logic and TMS integration.
Handles user synchronization, search, and data enrichment.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import utc_now

from app.repositories.user_repo import UserRepository
from app.core.tms_client import tms_client, TMSAPIException
from app.core.cache import cache_user_data, get_cached_user_data, invalidate_user_cache
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    TMSCurrentUserSchema,
    TMSPublicUserSchema,
    TMSSearchUserSchema,
    UserSearchResponse
)

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize user service."""
        self.db = db
        self.user_repo = UserRepository(db)

    def _compute_display_name(self, user_data: Dict[str, Any]) -> str:
        """
        Compute display name from user data.

        Priority: name > first_name + last_name > email

        Args:
            user_data: User data dictionary

        Returns:
            Display name string
        """
        if user_data.get("name"):
            return user_data["name"]

        first = user_data.get("first_name", user_data.get("firstName", ""))
        last = user_data.get("last_name", user_data.get("lastName", ""))

        if first and last:
            return f"{first} {last}"
        elif first:
            return first
        elif last:
            return last

        return user_data.get("email", "Unknown User")

    def _map_user_to_response(self, user: User, tms_data: Optional[Dict[str, Any]] = None) -> UserResponse:
        """
        Map User model to UserResponse schema.
        Enriches with TMS data if provided.

        Args:
            user: User model instance
            tms_data: Optional TMS user data for enrichment

        Returns:
            UserResponse schema
        """
        # Base data from local user model
        data = {
            "id": str(user.id),
            "tms_user_id": user.tms_user_id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": user.middle_name,
            "name": None,
            "image": user.image,
            "role": user.role,
            "position_title": user.position_title,
            "division": user.division,
            "department": user.department,
            "section": user.section,
            "custom_team": user.custom_team,
            "is_active": user.is_active,
            "is_leader": user.is_leader,
            "last_synced_at": user.last_synced_at,
            "created_at": user.created_at,
            "settings": user.settings_json,
        }

        # Enrich with TMS data if provided
        if tms_data:
            data.update({
                "name": tms_data.get("name"),
                "email": tms_data.get("email") or data["email"],
                "image": tms_data.get("image") or data["image"],
                "position_title": tms_data.get("positionTitle", tms_data.get("position_title")) or data["position_title"],
            })

        # Compute display name
        data["display_name"] = self._compute_display_name(data)

        return UserResponse(**data)

    async def get_current_user(
        self,
        token: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None
    ) -> UserResponse:
        """
        Get current authenticated user from TMS and sync locally.

        This is the main authentication flow:
        1. Fetch user from TMS /users/me using token or cookies
        2. Upsert to local database
        3. Return enriched user response

        Args:
            token: User's JWT token or session token (optional if cookies provided)
            cookies: Session cookies for NextAuth-based authentication

        Returns:
            UserResponse with full user data

        Raises:
            TMSAPIException: If authentication invalid or TMS unavailable
        """
        try:
            # Fetch current user from TMS (supports both token and cookies)
            tms_user_data = await tms_client.get_current_user_from_tms(
                token=token,
                cookies=cookies
            )
            tms_user_id = tms_user_data["id"]

            # Upsert to local database
            user = await self.user_repo.upsert_from_tms(tms_user_id, tms_user_data)
            await self.db.commit()

            # Return enriched response
            return self._map_user_to_response(user, tms_user_data)

        except TMSAPIException as e:
            logger.error(f"Failed to get current user from TMS: {e}")
            raise

    async def sync_user_from_tms(self, tms_user_id: str, force: bool = False) -> User:
        """
        Sync a single user from TMS to local database.

        Args:
            tms_user_id: TMS user ID
            force: Force sync even if recently synced

        Returns:
            Synced User instance

        Raises:
            TMSAPIException: If user not found or TMS unavailable
        """
        # Check if sync needed (unless forced)
        if not force:
            user = await self.user_repo.get_by_tms_user_id(tms_user_id)
            if user and user.last_synced_at:
                # Skip if synced within last 10 minutes
                if utc_now() - user.last_synced_at < timedelta(minutes=10):
                    logger.info(f"User {tms_user_id} recently synced, skipping")
                    return user

        try:
            # Fetch from TMS
            tms_user_data = await tms_client.get_user(tms_user_id, use_cache=True)

            # Upsert to database
            user = await self.user_repo.upsert_from_tms(tms_user_id, tms_user_data)
            await self.db.commit()

            logger.info(f"Successfully synced user {tms_user_id}")
            return user

        except TMSAPIException as e:
            logger.error(f"Failed to sync user {tms_user_id}: {e}")
            raise

    async def sync_users_batch(
        self,
        tms_user_ids: List[str],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Batch sync multiple users from TMS.

        Args:
            tms_user_ids: List of TMS user IDs to sync
            force: Force sync even if recently synced

        Returns:
            Dictionary with sync results (success_count, failed_count, errors)
        """
        if not tms_user_ids:
            return {"success_count": 0, "failed_count": 0, "errors": []}

        success_count = 0
        failed_count = 0
        errors = []

        for tms_user_id in tms_user_ids:
            try:
                await self.sync_user_from_tms(tms_user_id, force=force)
                success_count += 1
            except TMSAPIException as e:
                failed_count += 1
                errors.append(f"Failed to sync {tms_user_id}: {str(e)}")
                logger.error(f"Batch sync failed for {tms_user_id}: {e}")

        await self.db.commit()

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """
        Get user by local user ID.

        Args:
            user_id: Local user UUID

        Returns:
            UserResponse or None if not found
        """
        user = await self.user_repo.get(user_id)  # user_id is already a string
        if not user:
            return None

        # Try to get fresh TMS data from cache
        tms_data = await get_cached_user_data(user.tms_user_id)

        return self._map_user_to_response(user, tms_data)

    async def get_user_by_tms_id(self, tms_user_id: str) -> Optional[UserResponse]:
        """
        Get user by TMS user ID.
        Fetches from local DB and enriches with TMS cache.

        Args:
            tms_user_id: TMS user ID

        Returns:
            UserResponse or None if not found
        """
        user = await self.user_repo.get_by_tms_user_id(tms_user_id)
        if not user:
            # Try to fetch and sync from TMS
            try:
                user = await self.sync_user_from_tms(tms_user_id)
            except TMSAPIException:
                return None

        # Get fresh TMS data from cache
        tms_data = await get_cached_user_data(tms_user_id)

        return self._map_user_to_response(user, tms_data)

    async def search_users(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[UserResponse]:
        """
        Search users with TMS fallback.

        Strategy:
        1. Search local database first
        2. If insufficient results, search TMS API
        3. Sync TMS results to local DB
        4. Return combined results

        Args:
            query: Search query string
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of UserResponse
        """
        # Search local database
        local_users = await self.user_repo.search_users(
            query=query,
            filters=filters,
            limit=limit
        )

        # Convert to response format
        responses = [
            self._map_user_to_response(user)
            for user in local_users
        ]

        # If we have enough results, return them
        if len(responses) >= limit:
            return responses[:limit]

        # Otherwise, search TMS for additional results
        try:
            tms_results = await tms_client.search_users(query, limit=limit)
            tms_users = tms_results.get("users", [])

            # Sync TMS results to local DB (async, don't block)
            for tms_user_data in tms_users:
                tms_user_id = tms_user_data.get("id")
                if tms_user_id:
                    try:
                        user = await self.user_repo.upsert_from_tms(tms_user_id, tms_user_data)
                        # Add to responses if not already there
                        if not any(r.tms_user_id == tms_user_id for r in responses):
                            responses.append(self._map_user_to_response(user, tms_user_data))
                    except Exception as e:
                        logger.error(f"Failed to sync user {tms_user_id} during search: {e}")

            await self.db.commit()

        except TMSAPIException as e:
            logger.warning(f"TMS search failed, returning local results only: {e}")

        return responses[:limit]

    async def sync_active_users(self, hours_threshold: int = 12, batch_size: int = 50) -> Dict[str, Any]:
        """
        Background job: Sync users that haven't been synced recently.

        Args:
            hours_threshold: Hours since last sync to consider stale
            batch_size: Number of users to sync in one batch

        Returns:
            Dictionary with sync statistics
        """
        try:
            # Get users needing sync
            users_to_sync = await self.user_repo.get_users_needing_sync(
                hours_threshold=hours_threshold,
                limit=batch_size
            )

            if not users_to_sync:
                logger.info("No users need syncing")
                return {"synced": 0, "failed": 0, "skipped": 0}

            tms_user_ids = [user.tms_user_id for user in users_to_sync]
            logger.info(f"Syncing {len(tms_user_ids)} users from TMS")

            # Batch sync
            result = await self.sync_users_batch(tms_user_ids, force=True)

            logger.info(f"Sync completed: {result['success_count']} succeeded, {result['failed_count']} failed")
            return {
                "synced": result["success_count"],
                "failed": result["failed_count"],
                "skipped": 0
            }

        except Exception as e:
            logger.error(f"Background sync failed: {e}")
            return {"synced": 0, "failed": 0, "skipped": 0, "error": str(e)}

    async def invalidate_user_cache(self, tms_user_id: str) -> bool:
        """
        Invalidate cached user data.
        Use when user data changes in TMS.

        Args:
            tms_user_id: TMS user ID

        Returns:
            True if cache was invalidated
        """
        return await invalidate_user_cache(tms_user_id)
