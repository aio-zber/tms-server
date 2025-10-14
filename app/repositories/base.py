"""
Base repository with common CRUD operations.
All repositories should extend this class for database access.
"""
from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from uuid import UUID

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Provides generic database operations that can be reused across all repositories.
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            db: Async database session
        """
        self.model = model
        self.db = db

    async def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Model field values

        Returns:
            Created model instance

        Example:
            ```python
            user = await user_repo.create(tms_user_id="123", settings_json={})
            ```
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def get(self, id: UUID) -> Optional[ModelType]:
        """
        Get a record by ID.

        Args:
            id: Record UUID

        Returns:
            Model instance or None if not found

        Example:
            ```python
            message = await message_repo.get(message_id)
            if message:
                print(message.content)
            ```
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_many(
        self,
        ids: List[UUID],
        order_by: Optional[Any] = None
    ) -> List[ModelType]:
        """
        Get multiple records by IDs.

        Args:
            ids: List of record UUIDs
            order_by: Optional SQLAlchemy order_by clause

        Returns:
            List of model instances

        Example:
            ```python
            messages = await message_repo.get_many([id1, id2, id3])
            ```
        """
        query = select(self.model).where(self.model.id.in_(ids))

        if order_by is not None:
            query = query.order_by(order_by)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[Any] = None
    ) -> List[ModelType]:
        """
        Get all records with pagination.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip
            order_by: Optional SQLAlchemy order_by clause

        Returns:
            List of model instances

        Example:
            ```python
            messages = await message_repo.get_all(limit=50, offset=0)
            ```
        """
        query = select(self.model).limit(limit).offset(offset)

        if order_by is not None:
            query = query.order_by(order_by)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, id: UUID, **kwargs) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: Record UUID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None if not found

        Example:
            ```python
            updated_msg = await message_repo.update(
                msg_id,
                content="Updated content",
                is_edited=True
            )
            ```
        """
        await self.db.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
        )
        await self.db.flush()
        return await self.get(id)

    async def delete(self, id: UUID) -> bool:
        """
        Delete a record by ID (hard delete).

        Args:
            id: Record UUID

        Returns:
            True if deleted, False if not found

        Example:
            ```python
            deleted = await message_repo.delete(message_id)
            ```
        """
        result = await self.db.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """
        Check if a record exists.

        Args:
            id: Record UUID

        Returns:
            True if exists, False otherwise

        Example:
            ```python
            if await message_repo.exists(message_id):
                # Record exists
                pass
            ```
        """
        result = await self.db.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        )
        count = result.scalar()
        return count > 0

    async def count(self, **filters) -> int:
        """
        Count records matching filters.

        Args:
            **filters: Filter conditions

        Returns:
            Number of matching records

        Example:
            ```python
            count = await message_repo.count(conversation_id=conv_id)
            ```
        """
        query = select(func.count()).select_from(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        result = await self.db.execute(query)
        return result.scalar()

    async def filter_by(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[Any] = None,
        **filters
    ) -> List[ModelType]:
        """
        Filter records by conditions.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip
            order_by: Optional SQLAlchemy order_by clause
            **filters: Filter conditions

        Returns:
            List of matching model instances

        Example:
            ```python
            messages = await message_repo.filter_by(
                conversation_id=conv_id,
                sender_id=user_id,
                limit=50
            )
            ```
        """
        query = select(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        query = query.limit(limit).offset(offset)

        if order_by is not None:
            query = query.order_by(order_by)

        result = await self.db.execute(query)
        return list(result.scalars().all())
