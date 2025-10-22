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
                # Eager load reply_to AND its nested relationships
                selectinload(Message.reply_to).selectinload(Message.sender),
                selectinload(Message.reply_to).selectinload(Message.reactions),
                selectinload(Message.reply_to).selectinload(Message.statuses),
            )
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int = 10,
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
                # Eager load reply_to AND its nested relationships
                selectinload(Message.reply_to).selectinload(Message.sender),
                selectinload(Message.reply_to).selectinload(Message.reactions),
                selectinload(Message.reply_to).selectinload(Message.statuses),
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

        print(f"[MESSAGE_REPO] 🔍 Fetching messages for conversation: {conversation_id}")
        print(f"[MESSAGE_REPO] 🔍 Limit: {limit}, Cursor: {cursor}, Include deleted: {include_deleted}")
        
        # DEBUG: Get ALL messages to see total count and timestamps
        debug_query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
        )
        if not include_deleted:
            debug_query = debug_query.where(Message.deleted_at.is_(None))
        debug_query = debug_query.order_by(desc(Message.created_at), desc(Message.id))
        
        debug_result = await self.db.execute(debug_query)
        all_messages = list(debug_result.scalars().all())
        print(f"[MESSAGE_REPO] 📊 TOTAL messages in DB (non-deleted): {len(all_messages)}")
        if all_messages:
            print(f"[MESSAGE_REPO] 📊 Newest message: id={all_messages[0].id}, content='{all_messages[0].content[:30] if all_messages[0].content else 'NULL'}...', created_at={all_messages[0].created_at}")
            print(f"[MESSAGE_REPO] 📊 Oldest message: id={all_messages[-1].id}, content='{all_messages[-1].content[:30] if all_messages[-1].content else 'NULL'}...', created_at={all_messages[-1].created_at}")
            # Show all message IDs and timestamps for debugging
            print(f"[MESSAGE_REPO] 📊 All message timestamps:")
            for idx, msg in enumerate(all_messages):
                print(f"  [{idx}] id={msg.id}, created_at={msg.created_at}, deleted_at={msg.deleted_at}, content='{msg.content[:20] if msg.content else 'NULL'}...'")
        
        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        print(f"[MESSAGE_REPO] 📊 Query returned {len(messages)} messages (with limit={limit+1})")
        if messages:
            print(f"[MESSAGE_REPO] 📊 First returned: id={messages[0].id}, content='{messages[0].content[:30] if messages[0].content else 'NULL'}...', created_at={messages[0].created_at}")
            print(f"[MESSAGE_REPO] 📊 Last returned: id={messages[-1].id}, content='{messages[-1].content[:30] if messages[-1].content else 'NULL'}...', created_at={messages[-1].created_at}")
        
        # Check if there are more messages
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Get next cursor (ID of last message)
        next_cursor = messages[-1].id if messages and has_more else None

        print(f"[MESSAGE_REPO] ✅ Returning {len(messages)} messages, has_more={has_more}, next_cursor={next_cursor}")
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
        Search messages by text content with full-text search (Telegram/Messenger style).

        Features:
        - Full-text search with ts_query and ts_rank
        - Trigram similarity for fuzzy matching
        - Results ranked by relevance
        - Supports partial word matching

        Args:
            query: Search query string
            conversation_id: Optional conversation filter
            sender_id: Optional sender filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum results

        Returns:
            List of matching messages ordered by relevance
        """
        from sqlalchemy import func, text, case

        # Sanitize query for ts_query (remove special chars, handle spaces)
        sanitized_query = query.strip().replace("'", "''")
        # Convert spaces to AND operator for ts_query
        ts_query_str = ' & '.join(sanitized_query.split())

        # Build base query with eager loading
        search_query = select(Message).options(
            selectinload(Message.sender),
            selectinload(Message.reactions),
            selectinload(Message.statuses),
            # Eager load reply_to AND its nested relationships
            selectinload(Message.reply_to).selectinload(Message.sender),
            selectinload(Message.reply_to).selectinload(Message.reactions),
            selectinload(Message.reply_to).selectinload(Message.statuses),
        )

        # Apply filters first to narrow down search space
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

        # Compute relevance scores
        # 1. Full-text search rank (primary ranking)
        ts_rank = func.ts_rank(
            Message.content_tsv,
            func.to_tsquery('english', ts_query_str)
        ).label('ts_rank')

        # 2. Trigram similarity score (for fuzzy matching)
        trigram_similarity = func.similarity(
            Message.content,
            sanitized_query
        ).label('trigram_similarity')

        # 3. Combined relevance score (weighted)
        # ts_rank is weighted 70%, trigram 30% for best results
        combined_rank = (
            ts_rank * 0.7 + trigram_similarity * 0.3
        ).label('relevance')

        # Add ranking columns to query
        search_query = search_query.add_columns(
            ts_rank,
            trigram_similarity,
            combined_rank
        )

        # Apply search conditions with OR logic for better recall
        # Match if EITHER full-text search OR trigram similarity succeeds
        search_query = search_query.where(
            or_(
                # Full-text search match
                Message.content_tsv.op('@@')(
                    func.to_tsquery('english', ts_query_str)
                ),
                # Trigram similarity match (threshold: 0.1 = 10% similar)
                # Lower threshold catches more typos and partial matches
                func.similarity(Message.content, sanitized_query) > 0.1
            )
        )

        # Order by combined relevance score (highest first), then by recency
        search_query = search_query.order_by(
            desc(combined_rank),
            desc(Message.created_at)
        ).limit(limit)

        print(f"[MESSAGE_REPO] 🔍 Full-text search query: '{sanitized_query}'")
        print(f"[MESSAGE_REPO] 📊 Filters: conversation_id={conversation_id}, sender_id={sender_id}")

        result = await self.db.execute(search_query)

        # Extract messages from tuples (query returns (Message, ts_rank, trigram, combined))
        rows = result.all()
        messages = [row[0] for row in rows]

        # Log search results for debugging
        if messages:
            print(f"[MESSAGE_REPO] ✅ Found {len(messages)} messages")
            for i, row in enumerate(rows[:3]):  # Show top 3 results
                msg, ts_r, tg_sim, relevance = row
                print(f"  [{i+1}] relevance={relevance:.3f} (ts={ts_r:.3f}, tg={tg_sim:.3f}): '{msg.content[:50]}...'")
        else:
            print(f"[MESSAGE_REPO] ⚠️ No messages found for query: '{sanitized_query}'")

        return messages

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

        Uses Redis caching for performance (Messenger/Telegram pattern):
        - Cache hit: O(1) ~1ms response time
        - Cache miss: Query DB, then cache result
        - TTL: 60 seconds
        - Invalidated on: message read, new message, conversation open

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Number of unread messages
        """
        from app.core.cache import get_cached_unread_count, cache_unread_count

        # Try cache first (fast path)
        conversation_id_str = str(conversation_id)
        user_id_str = str(user_id)

        cached_count = await get_cached_unread_count(user_id_str, conversation_id_str)
        if cached_count is not None:
            print(f"[MESSAGE_REPO] ⚡ Cache HIT for unread count: user={user_id_str[:8]}, conv={conversation_id_str[:8]}, count={cached_count}")
            return cached_count

        print(f"[MESSAGE_REPO] 💾 Cache MISS for unread count, querying DB...")

        # Cache miss - query database
        # Optimized query using partial index on message_status
        # This uses idx_message_status_user_unread for fast lookup
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
        # Uses idx_messages_conversation_created_id for fast filtering
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
        count = result.scalar() or 0

        # Cache the result for 60 seconds
        await cache_unread_count(user_id_str, conversation_id_str, count)
        print(f"[MESSAGE_REPO] ✅ Cached unread count: user={user_id_str[:8]}, conv={conversation_id_str[:8]}, count={count}")

        return count


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

    async def mark_messages_as_delivered(
        self,
        conversation_id: UUID,
        user_id: UUID,
        message_ids: Optional[List[UUID]] = None
    ) -> int:
        """
        Mark messages as delivered (SENT → DELIVERED) for a user in a conversation.

        Implements Telegram/Messenger pattern:
        - If message_ids provided: marks only those messages
        - If message_ids is None: marks ALL SENT messages in conversation

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            message_ids: Optional list of specific message UUIDs

        Returns:
            Number of statuses updated
        """
        from app.models.message import Message

        if message_ids:
            # Mark specific messages
            count = 0
            for message_id in message_ids:
                # Check current status - only update if SENT
                stmt = select(MessageStatus).where(
                    and_(
                        MessageStatus.message_id == message_id,
                        MessageStatus.user_id == user_id
                    )
                )
                result = await self.db.execute(stmt)
                status = result.scalar_one_or_none()

                if status and status.status == MessageStatusType.SENT:
                    await self.upsert_status(message_id, user_id, MessageStatusType.DELIVERED)
                    count += 1
            return count
        else:
            # Mark all SENT messages in conversation as DELIVERED
            # More efficient bulk update using SQL
            from sqlalchemy import update

            # Get all message IDs in conversation that have SENT status for this user
            stmt = (
                select(MessageStatus.message_id)
                .join(Message, Message.id == MessageStatus.message_id)
                .where(
                    and_(
                        Message.conversation_id == conversation_id,
                        MessageStatus.user_id == user_id,
                        MessageStatus.status == MessageStatusType.SENT,
                        Message.deleted_at.is_(None)
                    )
                )
            )
            result = await self.db.execute(stmt)
            sent_message_ids = [row[0] for row in result.all()]

            if not sent_message_ids:
                return 0

            # Bulk update to DELIVERED
            update_stmt = (
                update(MessageStatus)
                .where(
                    and_(
                        MessageStatus.message_id.in_(sent_message_ids),
                        MessageStatus.user_id == user_id,
                        MessageStatus.status == MessageStatusType.SENT
                    )
                )
                .values(
                    status=MessageStatusType.DELIVERED,
                    updated_at=datetime.utcnow()
                )
            )
            result = await self.db.execute(update_stmt)
            await self.db.flush()

            return result.rowcount if result.rowcount else 0


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
