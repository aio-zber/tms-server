"""
Message repository for database operations.
Handles CRUD and query operations for messages, statuses, and reactions.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageStatus, MessageReaction, MessageStatusType
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for message database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize message repository."""
        super().__init__(Message, db)

    async def get_with_relations(self, message_id: UUID) -> Optional[Message]:
        """
        Get message with all related data (sender, reactions, statuses).

        Args:
            message_id: Message UUID

        Returns:
            Message with relations or None
        """
        result = await self.db.execute(
            select(Message)
            .options(
                selectinload(Message.sender),
                selectinload(Message.reactions),
                selectinload(Message.statuses),
                selectinload(Message.reply_to)
            )
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int = 50,
        cursor: Optional[UUID] = None,
        include_deleted: bool = False
    ) -> Tuple[List[Message], Optional[UUID], bool]:
        """
        Get messages for a conversation with cursor-based pagination.

        Args:
            conversation_id: Conversation UUID
            limit: Number of messages to return
            cursor: Last message ID for pagination
            include_deleted: Include soft-deleted messages

        Returns:
            Tuple of (messages, next_cursor, has_more)
        """
        query = (
            select(Message)
            .options(
                selectinload(Message.sender),
                selectinload(Message.reactions),
                selectinload(Message.statuses),
                selectinload(Message.reply_to)
            )
            .where(Message.conversation_id == conversation_id)
        )

        # Exclude deleted messages unless explicitly requested
        if not include_deleted:
            query = query.where(Message.deleted_at.is_(None))

        # Apply cursor pagination
        if cursor:
            cursor_msg = await self.get(cursor)
            if cursor_msg:
                # For stable pagination with identical timestamps, use both created_at and id
                query = query.where(
                    or_(
                        Message.created_at < cursor_msg.created_at,
                        and_(
                            Message.created_at == cursor_msg.created_at,
                            Message.id < cursor_msg.id
                        )
                    )
                )

        # Order by created_at descending (newest first), then by id for stable ordering
        # This ensures consistent order even when messages have identical timestamps
        query = query.order_by(desc(Message.created_at), desc(Message.id)).limit(limit + 1)

        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        # Check if there are more messages
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Get next cursor (ID of last message)
        next_cursor = messages[-1].id if messages and has_more else None

        return messages, next_cursor, has_more

    async def search_messages(
        self,
        query: str,
        conversation_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Message]:
        """
        Search messages by text content with filters.

        Args:
            query: Search query string
            conversation_id: Optional conversation filter
            sender_id: Optional sender filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum results

        Returns:
            List of matching messages
        """
        search_query = select(Message).options(
            selectinload(Message.sender)
        )

        # Text search (case-insensitive partial match)
        search_query = search_query.where(
            Message.content.ilike(f"%{query}%")
        )

        # Apply filters
        if conversation_id:
            search_query = search_query.where(Message.conversation_id == conversation_id)

        if sender_id:
            search_query = search_query.where(Message.sender_id == sender_id)

        if start_date:
            search_query = search_query.where(Message.created_at >= start_date)

        if end_date:
            search_query = search_query.where(Message.created_at <= end_date)

        # Exclude deleted messages
        search_query = search_query.where(Message.deleted_at.is_(None))

        # Order by relevance (newest first for now)
        search_query = search_query.order_by(desc(Message.created_at)).limit(limit)

        result = await self.db.execute(search_query)
        return list(result.scalars().all())

    async def soft_delete(self, message_id: UUID) -> Optional[Message]:
        """
        Soft delete a message (set deleted_at timestamp).

        Args:
            message_id: Message UUID

        Returns:
            Deleted message or None
        """
        return await self.update(message_id, deleted_at=datetime.utcnow())

    async def get_unread_count(
        self,
        conversation_id: UUID,
        user_id: UUID
    ) -> int:
        """
        Get count of unread messages in a conversation for a user.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Number of unread messages
        """
        # Subquery to get read message IDs
        read_subquery = (
            select(MessageStatus.message_id)
            .where(
                and_(
                    MessageStatus.user_id == user_id,
                    MessageStatus.status == MessageStatusType.READ
                )
            )
        )

        # Count messages not in read subquery
        query = (
            select(func.count())
            .select_from(Message)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_id != user_id,  # Don't count own messages
                    Message.deleted_at.is_(None),
                    Message.id.notin_(read_subquery)
                )
            )
        )

        result = await self.db.execute(query)
        return result.scalar() or 0


class MessageStatusRepository(BaseRepository[MessageStatus]):
    """Repository for message status operations."""

    def __init__(self, db: AsyncSession):
        """Initialize message status repository."""
        super().__init__(MessageStatus, db)

    async def upsert_status(
        self,
        message_id: UUID,
        user_id: UUID,
        status: MessageStatusType
    ) -> MessageStatus:
        """
        Create or update message status for a user.

        Args:
            message_id: Message UUID
            user_id: User UUID
            status: Status type (sent, delivered, read)

        Returns:
            Message status instance
        """
        # Check if status exists
        result = await self.db.execute(
            select(MessageStatus).where(
                and_(
                    MessageStatus.message_id == message_id,
                    MessageStatus.user_id == user_id
                )
            )
        )
        existing_status = result.scalar_one_or_none()

        if existing_status:
            # Update existing status
            existing_status.status = status
            existing_status.timestamp = datetime.utcnow()
            await self.db.flush()
            return existing_status
        else:
            # Create new status
            new_status = MessageStatus(
                message_id=message_id,
                user_id=user_id,
                status=status,
                timestamp=datetime.utcnow()
            )
            self.db.add(new_status)
            await self.db.flush()
            return new_status

    async def mark_messages_as_delivered(
        self,
        message_ids: List[UUID],
        user_id: UUID
    ) -> int:
        """
        Mark multiple messages as delivered for a user.

        Args:
            message_ids: List of message UUIDs
            user_id: User UUID

        Returns:
            Number of statuses updated
        """
        count = 0
        for message_id in message_ids:
            await self.upsert_status(message_id, user_id, MessageStatusType.DELIVERED)
            count += 1
        return count

    async def mark_messages_as_read(
        self,
        message_ids: List[UUID],
        user_id: UUID
    ) -> int:
        """
        Mark multiple messages as read for a user.

        Args:
            message_ids: List of message UUIDs
            user_id: User UUID

        Returns:
            Number of statuses updated
        """
        count = 0
        for message_id in message_ids:
            await self.upsert_status(message_id, user_id, MessageStatusType.READ)
            count += 1
        return count


class MessageReactionRepository(BaseRepository[MessageReaction]):
    """Repository for message reaction operations."""

    def __init__(self, db: AsyncSession):
        """Initialize message reaction repository."""
        super().__init__(MessageReaction, db)

    async def add_reaction(
        self,
        message_id: UUID,
        user_id: UUID,
        emoji: str
    ) -> Optional[MessageReaction]:
        """
        Add a reaction to a message.

        Args:
            message_id: Message UUID
            user_id: User UUID
            emoji: Emoji string

        Returns:
            Created reaction or None if already exists
        """
        # Check if reaction already exists
        result = await self.db.execute(
            select(MessageReaction).where(
                and_(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id,
                    MessageReaction.emoji == emoji
                )
            )
        )

        if result.scalar_one_or_none():
            return None  # Reaction already exists

        # Create new reaction
        reaction = await self.create(
            message_id=message_id,
            user_id=user_id,
            emoji=emoji
        )
        return reaction

    async def remove_reaction(
        self,
        message_id: UUID,
        user_id: UUID,
        emoji: str
    ) -> bool:
        """
        Remove a reaction from a message.

        Args:
            message_id: Message UUID
            user_id: User UUID
            emoji: Emoji string

        Returns:
            True if removed, False if not found
        """
        result = await self.db.execute(
            select(MessageReaction).where(
                and_(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id,
                    MessageReaction.emoji == emoji
                )
            )
        )

        reaction = result.scalar_one_or_none()
        if reaction:
            await self.db.delete(reaction)
            await self.db.flush()
            return True
        return False

    async def get_message_reactions(self, message_id: UUID) -> List[MessageReaction]:
        """
        Get all reactions for a message.

        Args:
            message_id: Message UUID

        Returns:
            List of reactions
        """
        result = await self.db.execute(
            select(MessageReaction)
            .where(MessageReaction.message_id == message_id)
            .order_by(MessageReaction.created_at)
        )
        return list(result.scalars().all())
