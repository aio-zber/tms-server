"""
User repository for database operations.
Handles user CRUD, syncing from TMS, and search operations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
# UUID import removed - using str for ID types

from app.utils.datetime_utils import utc_now

from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for user database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize user repository."""
        super().__init__(User, db)

    async def get_by_tms_user_id(self, tms_user_id: str) -> Optional[User]:
        """
        Get user by TMS user ID.

        Args:
            tms_user_id: TMS user ID

        Returns:
            User instance or None

        Example:
            ```python
            user = await user_repo.get_by_tms_user_id("tms-123")
            ```
        """
        result = await self.db.execute(
            select(User).where(User.tms_user_id == tms_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            User instance or None
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def upsert_from_tms(
        self,
        tms_user_id: str,
        tms_data: Dict[str, Any]
    ) -> User:
        """
        Upsert (insert or update) user from TMS data.

        Uses a DUAL-IDENTIFIER strategy to handle both scenarios:
        - TMS ID changes but email stays same (e.g., TMS database reseed)
        - Email changes but TMS ID stays same (e.g., user updates email in TMS)

        Priority order:
        1. First, try to match by TMS user ID (primary identifier)
        2. If not found, try to match by EMAIL (fallback identifier)
        3. If neither found, create new user

        This ensures conversations and messages are preserved regardless of
        which identifier changes in TMS.

        Args:
            tms_user_id: TMS user ID (may be new/different from stored ID)
            tms_data: User data from TMS API

        Returns:
            User instance (created or updated)

        Example:
            ```python
            user = await user_repo.upsert_from_tms("tms-123", tms_user_data)
            ```
        """
        # Map TMS data to local user fields
        # GCGC uses "name" (single field) instead of firstName/lastName
        # So we need to split the name or use it as-is
        full_name = tms_data.get("name", "")
        name_parts = full_name.split(" ", 1) if full_name else []

        # Try to get firstName/lastName, but fallback to splitting "name"
        first_name = (
            tms_data.get("firstName") or
            tms_data.get("first_name") or
            (name_parts[0] if len(name_parts) > 0 else None)
        )
        last_name = (
            tms_data.get("lastName") or
            tms_data.get("last_name") or
            (name_parts[1] if len(name_parts) > 1 else None)
        )

        email = tms_data.get("email")

        print(f"[USER_REPO] 👤 Syncing user: tms_id={tms_user_id}, email='{email}', name='{full_name}'")

        # STEP 1: Try to find existing user by TMS ID first (handles email changes)
        existing_user = await self.get_by_tms_user_id(tms_user_id)
        if existing_user:
            print(f"[USER_REPO] ✅ Found existing user by TMS ID: {tms_user_id}")
            if existing_user.email != email:
                print(f"[USER_REPO] 📝 Email changed: {existing_user.email} -> {email}")

        # STEP 2: If not found by TMS ID, try to find by EMAIL (handles TMS ID changes)
        if not existing_user and email:
            existing_user = await self.get_by_email(email)
            if existing_user:
                print(f"[USER_REPO] ✅ Found existing user by email: {email} (current id={existing_user.id})")
                print(f"[USER_REPO] ⚠️ TMS ID changed: {existing_user.tms_user_id} -> {tms_user_id}")
                print(f"[USER_REPO] 📝 Keeping existing user ID to preserve conversations/messages")

        # STEP 3: If user exists (by either identifier), UPDATE that user
        if existing_user:
            # Update existing user, keeping the original ID to preserve relationships
            # Only update tms_user_id if we found by TMS ID (not email fallback)
            # This keeps the stable ID that has all the foreign key references
            existing_user.email = email
            existing_user.username = tms_data.get("username")
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.middle_name = tms_data.get("middleName") or tms_data.get("middle_name")
            existing_user.image = tms_data.get("image")
            existing_user.contact_number = tms_data.get("contactNumber") or tms_data.get("contact_number")
            existing_user.role = tms_data.get("role")
            existing_user.position_title = tms_data.get("positionTitle") or tms_data.get("position_title")
            existing_user.division = tms_data.get("division")
            existing_user.department = tms_data.get("department")
            existing_user.section = tms_data.get("section")
            existing_user.custom_team = tms_data.get("customTeam") or tms_data.get("custom_team")
            existing_user.hierarchy_level = tms_data.get("hierarchyLevel") or tms_data.get("hierarchy_level")
            existing_user.reports_to_id = tms_data.get("reportsToId") or tms_data.get("reports_to_id")
            existing_user.is_active = tms_data.get("isActive", tms_data.get("is_active", True))
            existing_user.is_leader = tms_data.get("isLeader", tms_data.get("is_leader", False))
            existing_user.last_synced_at = utc_now()
            existing_user.updated_at = utc_now()

            await self.db.flush()
            await self.db.refresh(existing_user)
            print(f"[USER_REPO] ✅ Updated existing user: {existing_user.id}")
            return existing_user

        # STEP 4: No existing user found - create new user with tms_user_id
        print(f"[USER_REPO] 🆕 Creating new user with id={tms_user_id}")

        user_data = {
            "id": tms_user_id,  # Use TMS user ID (CUID format) as primary key
            "tms_user_id": tms_user_id,
            "email": email,
            "username": tms_data.get("username"),
            "first_name": first_name,
            "last_name": last_name,
            "middle_name": tms_data.get("middleName") or tms_data.get("middle_name"),
            "image": tms_data.get("image"),
            "contact_number": tms_data.get("contactNumber") or tms_data.get("contact_number"),
            "role": tms_data.get("role"),
            "position_title": tms_data.get("positionTitle") or tms_data.get("position_title"),
            "division": tms_data.get("division"),
            "department": tms_data.get("department"),
            "section": tms_data.get("section"),
            "custom_team": tms_data.get("customTeam") or tms_data.get("custom_team"),
            "hierarchy_level": tms_data.get("hierarchyLevel") or tms_data.get("hierarchy_level"),
            "reports_to_id": tms_data.get("reportsToId") or tms_data.get("reports_to_id"),
            "is_active": tms_data.get("isActive", tms_data.get("is_active", True)),
            "is_leader": tms_data.get("isLeader", tms_data.get("is_leader", False)),
            "last_synced_at": utc_now(),
        }

        # Use PostgreSQL UPSERT for new users (in case of race conditions)
        stmt = insert(User).values(**user_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tms_user_id"],  # Unique constraint on tms_user_id
            set_={
                **{k: v for k, v in user_data.items() if k not in ["id", "tms_user_id"]},
                "updated_at": utc_now(),
            }
        ).returning(User)

        result = await self.db.execute(stmt)
        await self.db.flush()
        user = result.scalar_one()
        await self.db.refresh(user)
        return user

    async def batch_upsert_from_tms(
        self,
        users_data: List[Dict[str, Any]]
    ) -> List[User]:
        """
        Batch upsert multiple users from TMS data.
        More efficient than upserting one by one.

        Args:
            users_data: List of TMS user data dictionaries

        Returns:
            List of upserted User instances

        Example:
            ```python
            users = await user_repo.batch_upsert_from_tms([
                {"id": "tms-1", "email": "user1@example.com", ...},
                {"id": "tms-2", "email": "user2@example.com", ...},
            ])
            ```
        """
        if not users_data:
            return []

        upserted_users = []
        for tms_data in users_data:
            tms_user_id = tms_data.get("id")
            if tms_user_id:
                user = await self.upsert_from_tms(tms_user_id, tms_data)
                upserted_users.append(user)

        return upserted_users

    async def search_users(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[User]:
        """
        Search users by name, email, or username.
        Supports additional filters for division, department, role, etc.

        Args:
            query: Search query string
            filters: Optional filters (division, department, role, is_active)
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List of matching User instances

        Example:
            ```python
            users = await user_repo.search_users(
                "john",
                filters={"division": "Engineering", "is_active": True},
                limit=10
            )
            ```
        """
        stmt = select(User)

        # Text search on name, email, username
        if query and query.strip():
            search_term = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term),
                    func.lower(User.email).like(search_term),
                    func.lower(User.username).like(search_term),
                )
            )

        # Apply filters
        if filters:
            if "division" in filters:
                stmt = stmt.where(User.division == filters["division"])
            if "department" in filters:
                stmt = stmt.where(User.department == filters["department"])
            if "section" in filters:
                stmt = stmt.where(User.section == filters["section"])
            if "role" in filters:
                stmt = stmt.where(User.role == filters["role"])
            if "is_active" in filters:
                stmt = stmt.where(User.is_active == filters["is_active"])
            if "is_leader" in filters:
                stmt = stmt.where(User.is_leader == filters["is_leader"])

        # Pagination and ordering
        stmt = stmt.order_by(User.first_name, User.last_name).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_users(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """
        Get all active users.

        Args:
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List of active User instances
        """
        result = await self.db.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.first_name, User.last_name)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_users_needing_sync(
        self,
        hours_threshold: int = 12,
        limit: int = 100
    ) -> List[User]:
        """
        Get users that need syncing (not synced in X hours).

        Args:
            hours_threshold: Hours since last sync
            limit: Maximum number of results

        Returns:
            List of User instances needing sync
        """
        threshold_time = utc_now() - datetime.timedelta(hours=hours_threshold)

        result = await self.db.execute(
            select(User)
            .where(
                or_(
                    User.last_synced_at == None,
                    User.last_synced_at < threshold_time
                )
            )
            .order_by(User.last_synced_at.asc().nullsfirst())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_division(self) -> Dict[str, int]:
        """
        Count users grouped by division.

        Returns:
            Dictionary mapping division to count
        """
        result = await self.db.execute(
            select(User.division, func.count(User.id))
            .where(User.is_active == True)
            .group_by(User.division)
        )
        return {division: count for division, count in result.all()}

    async def count_by_role(self) -> Dict[str, int]:
        """
        Count users grouped by role.

        Returns:
            Dictionary mapping role to count
        """
        result = await self.db.execute(
            select(User.role, func.count(User.id))
            .where(User.is_active == True)
            .group_by(User.role)
        )
        return {role: count for role, count in result.all()}
