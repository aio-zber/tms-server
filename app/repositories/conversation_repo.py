"""
Conversation repository for database operations.
Handles conversations, members, and related queries.
"""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
# UUID import removed - using str for ID types

from app.utils.datetime_utils import utc_now

from sqlalchemy import select, func, and_, or_, desc, delete, literal, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, aliased

from app.models.conversation import Conversation, ConversationMember, ConversationType, ConversationRole
from app.models.message import Message
from app.models.user import User
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation database operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Conversation, db)

    async def get_with_relations(
        self, conversation_id: str, include_members: bool = True
    ) -> Optional[Conversation]:
        """
        Get conversation with related data loaded.

        Args:
            conversation_id: Conversation UUID
            include_members: Whether to load members

        Returns:
            Conversation with relations or None
        """
        query = select(Conversation).where(Conversation.id == conversation_id)

        if include_members:
            query = query.options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.creator)
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None
    ) -> Tuple[List[Conversation], Optional[str], bool]:
        """
        Get conversations for a user with cursor-based pagination.

        Args:
            user_id: User UUID
            limit: Maximum conversations to return
            cursor: Cursor for pagination (conversation_id)

        Returns:
            Tuple of (conversations, next_cursor, has_more)
        """
        # Subquery to get user's conversation IDs
        member_subquery = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
        )

        query = (
            select(Conversation)
            .where(Conversation.id.in_(member_subquery))
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.creator)
            )
        )

        # Cursor-based pagination using updated_at
        if cursor:
            cursor_conv = await self.get(cursor)
            if cursor_conv:
                query = query.where(Conversation.updated_at < cursor_conv.updated_at)

        query = query.order_by(desc(Conversation.updated_at)).limit(limit + 1)

        result = await self.db.execute(query)
        conversations = list(result.scalars().all())

        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        next_cursor = conversations[-1].id if conversations and has_more else None

        return conversations, next_cursor, has_more

    async def create_with_members(
        self,
        type: ConversationType,
        creator_id: str,
        member_ids: List[str],
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Conversation:
        """
        Create conversation with members in a single transaction.

        Args:
            type: Conversation type (dm/group)
            creator_id: Creator user ID
            member_ids: List of OTHER member user IDs (should NOT include creator)
            name: Optional conversation name
            avatar_url: Optional avatar URL

        Returns:
            Created conversation with members

        Raises:
            ValueError: If creator is in member_ids (safety check)
        """
        # Create conversation
        conversation = Conversation(
            type=type,
            name=name,
            avatar_url=avatar_url,
            created_by=creator_id
        )
        self.db.add(conversation)
        await self.db.flush()

        # Add creator as admin
        creator_member = ConversationMember(
            conversation_id=conversation.id,
            user_id=creator_id,
            role=ConversationRole.ADMIN,
            last_read_at=utc_now()
        )
        self.db.add(creator_member)

        # Add other members (member_ids should already exclude creator)
        for member_id in member_ids:
            # Safety check: ensure not adding creator twice
            if member_id == creator_id:
                raise ValueError(f"Creator {creator_id} should not be in member_ids - they are added automatically as admin")

            member = ConversationMember(
                conversation_id=conversation.id,
                user_id=member_id,
                role=ConversationRole.MEMBER
            )
            self.db.add(member)

        await self.db.flush()
        await self.db.refresh(conversation)

        return await self.get_with_relations(conversation.id)

    async def find_dm_conversation(
        self, user1_id: str, user2_id: str
    ) -> Optional[Conversation]:
        """
        Find existing DM conversation between two users.

        Args:
            user1_id: First user UUID
            user2_id: Second user UUID

        Returns:
            DM conversation or None
        """
        # Subquery for user1's conversations
        user1_convs = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user1_id)
        )

        # Subquery for user2's conversations
        user2_convs = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user2_id)
        )

        # Find DM conversations that both users are in
        query = (
            select(Conversation)
            .where(
                and_(
                    Conversation.type == ConversationType.DM,
                    Conversation.id.in_(user1_convs),
                    Conversation.id.in_(user2_convs)
                )
            )
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user)
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_conversation(
        self,
        conversation_id: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        avatar_oss_key: Optional[str] = None,
    ) -> Optional[Conversation]:
        """
        Update conversation details.

        Args:
            conversation_id: Conversation UUID
            name: Updated name
            avatar_url: Updated avatar URL
            avatar_oss_key: OSS object key for avatar (enables URL refresh on fetch)

        Returns:
            Updated conversation or None
        """
        updates = {}
        if name is not None:
            updates['name'] = name
        if avatar_url is not None:
            updates['avatar_url'] = avatar_url
        if avatar_oss_key is not None:
            updates['avatar_oss_key'] = avatar_oss_key

        if updates:
            updates['updated_at'] = utc_now()
            return await self.update(conversation_id, **updates)

        return await self.get_with_relations(conversation_id)

    async def get_last_message(self, conversation_id: str) -> Optional[Message]:
        """
        Get the last message in a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Last message or None
        """
        query = (
            select(Message)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.deleted_at.is_(None)
                )
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_last_messages_batch(
        self, conversation_ids: List[str]
    ) -> dict[str, Message]:
        """
        Get the last non-deleted message for each conversation in one query.

        Messenger pattern: subquery selects the max created_at per conversation,
        then joins back to get the full message row. Single DB round-trip.

        Args:
            conversation_ids: List of conversation UUIDs

        Returns:
            Dict mapping conversation_id → last Message (omits convs with no messages)
        """
        if not conversation_ids:
            return {}

        # Subquery: max created_at per conversation
        latest_subq = (
            select(
                Message.conversation_id,
                func.max(Message.created_at).label("max_created_at"),
            )
            .where(
                and_(
                    Message.conversation_id.in_(conversation_ids),
                    Message.deleted_at.is_(None),
                )
            )
            .group_by(Message.conversation_id)
            .subquery()
        )

        # Join back to get full message rows matching the max timestamp
        query = (
            select(Message)
            .join(
                latest_subq,
                and_(
                    Message.conversation_id == latest_subq.c.conversation_id,
                    Message.created_at == latest_subq.c.max_created_at,
                    Message.deleted_at.is_(None),
                ),
            )
        )

        result = await self.db.execute(query)
        messages = result.scalars().all()
        # If two messages share the exact same created_at (rare), keep one
        seen: dict[str, Message] = {}
        for msg in messages:
            if msg.conversation_id not in seen:
                seen[msg.conversation_id] = msg
        return seen

    async def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 20
    ) -> List[Conversation]:
        """
        Search conversations by name, member names, OR message content using PostgreSQL full-text search.

        Implements hybrid search strategy similar to Telegram/Messenger:
        - Uses trigram similarity for fuzzy matching
        - Searches conversation name (60% weight) for groups
        - Searches member names (40% weight) - INCLUDES DM partner names
        - Searches message content in conversations (Telegram/Messenger pattern)
        - For DMs, searches the OTHER participant's name
        - Only returns conversations the user is a member of

        Uses simple two-step approach (no UNION) for better SQL compatibility.

        Args:
            user_id: User UUID (must be a member of returned conversations)
            query: Search query string
            limit: Maximum results to return (default 20)

        Returns:
            List of conversations ordered by relevance score
        """
        # Normalize search query for trigram matching
        search_term = query.strip().lower()

        print(f"[SEARCH] 🔍 Searching conversations for user {user_id} with query: '{search_term}'")

        # Subquery to get user's conversation IDs
        member_subquery = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
        )

        # Alias for member users to search
        MemberUser = aliased(User)

        # Step 1: Get conversation IDs from name/member matches
        name_match_query = (
            select(Conversation.id.distinct())
            .select_from(Conversation)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id
            )
            .join(
                MemberUser,
                MemberUser.id == ConversationMember.user_id
            )
            .where(
                and_(
                    # Only user's conversations
                    Conversation.id.in_(member_subquery),
                    # Match either conversation name or member names
                    or_(
                        # Conversation name match (for groups)
                        and_(
                            Conversation.name.isnot(None),
                            func.lower(Conversation.name).like(f"%{search_term}%")
                        ),
                        # Member name match - EXCLUDE current user (works for both groups and DMs)
                        and_(
                            MemberUser.id != user_id,  # Don't match own name
                            func.lower(
                                func.concat(MemberUser.first_name, ' ', MemberUser.last_name)
                            ).like(f"%{search_term}%")
                        ),
                        # Trigram similarity for conversation name
                        and_(
                            Conversation.name.isnot(None),
                            func.similarity(func.lower(Conversation.name), search_term) > 0.3
                        ),
                        # Trigram similarity for member names - EXCLUDE current user (lower threshold for DMs)
                        and_(
                            MemberUser.id != user_id,  # Don't match own name
                            func.similarity(
                                func.lower(
                                    func.concat(MemberUser.first_name, ' ', MemberUser.last_name)
                                ),
                                search_term
                            ) > 0.2  # Lower threshold to catch more DM matches
                        )
                    )
                )
            )
        )

        result = await self.db.execute(name_match_query)
        conv_ids_from_names = [row[0] for row in result.all()]
        print(f"[SEARCH] 📝 Found {len(conv_ids_from_names)} conversations from name/member matches")
        if conv_ids_from_names:
            print(f"[SEARCH] 📝 Name match conversation IDs: {[str(cid)[:8] for cid in conv_ids_from_names]}")

        # Step 2: Get conversation IDs from message content matches
        message_match_query = (
            select(Conversation.id.distinct())
            .select_from(Conversation)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                and_(
                    # Only user's conversations
                    Conversation.id.in_(member_subquery),
                    # Message not deleted
                    Message.deleted_at.is_(None),
                    # Match message content
                    or_(
                        # ILIKE for partial match
                        func.lower(Message.content).like(f"%{search_term}%"),
                        # Trigram similarity for fuzzy match
                        func.similarity(func.lower(Message.content), search_term) > 0.2
                    )
                )
            )
        )

        result = await self.db.execute(message_match_query)
        conv_ids_from_messages = [row[0] for row in result.all()]
        print(f"[SEARCH] 💬 Found {len(conv_ids_from_messages)} conversations from message content matches")
        if conv_ids_from_messages:
            print(f"[SEARCH] 💬 Message match conversation IDs: {[str(cid)[:8] for cid in conv_ids_from_messages]}")

        # Step 3: Merge and deduplicate conversation IDs
        all_conv_ids = list(set(conv_ids_from_names + conv_ids_from_messages))
        print(f"[SEARCH] 🔄 Merged to {len(all_conv_ids)} unique conversation IDs")

        if not all_conv_ids:
            print(f"[SEARCH] ⚠️ No conversations found for query: '{search_term}'")
            return []

        print(f"[SEARCH] 📋 All unique conversation IDs: {[str(cid)[:8] for cid in all_conv_ids]}")

        # Step 4: Fetch full conversation objects with relations
        # Order by updated_at (most recent first)
        final_query = (
            select(Conversation)
            .where(Conversation.id.in_(all_conv_ids))
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.creator)
            )
        )

        result = await self.db.execute(final_query)
        conversations = list(result.scalars().all())

        print(f"[SEARCH] ✅ Found {len(conversations)} conversations total (name/member + message content)")
        for conv in conversations[:3]:  # Show first 3 results
            print(f"  - {conv.type}: {conv.name or 'DM'} (id: {str(conv.id)[:8]})")

        return conversations


class ConversationMemberRepository:
    """Repository for conversation member operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(
        self, conversation_id: str, user_id: str
    ) -> Optional[ConversationMember]:
        """
        Get conversation member record.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            ConversationMember or None
        """
        result = await self.db.execute(
            select(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id
                )
            )
            .options(selectinload(ConversationMember.user))
        )
        return result.scalar_one_or_none()

    async def is_member(self, conversation_id: str, user_id: str) -> bool:
        """
        Check if user is a member of conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            True if member, False otherwise
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id
                )
            )
        )
        return result.scalar() > 0

    async def is_admin(self, conversation_id: str, user_id: str) -> bool:
        """
        Check if user is an admin of conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            True if admin, False otherwise
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                    ConversationMember.role == ConversationRole.ADMIN
                )
            )
        )
        return result.scalar() > 0

    async def get_members(
        self, conversation_id: str
    ) -> List[ConversationMember]:
        """
        Get all members of a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of conversation members
        """
        result = await self.db.execute(
            select(ConversationMember)
            .where(ConversationMember.conversation_id == conversation_id)
            .options(selectinload(ConversationMember.user))
        )
        return list(result.scalars().all())

    async def get_member_count(self, conversation_id: str) -> int:
        """
        Get total member count for conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Number of members
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(ConversationMember)
            .where(ConversationMember.conversation_id == conversation_id)
        )
        return result.scalar()

    async def add_members(
        self, conversation_id: str, user_ids: List[str]
    ) -> int:
        """
        Add multiple members to conversation.

        Args:
            conversation_id: Conversation UUID
            user_ids: List of user IDs to add

        Returns:
            Number of members added
        """
        added_count = 0

        for user_id in user_ids:
            # Check if already a member
            if await self.is_member(conversation_id, user_id):
                continue

            member = ConversationMember(
                conversation_id=conversation_id,
                user_id=user_id,
                role=ConversationRole.MEMBER
            )
            self.db.add(member)
            added_count += 1

        await self.db.flush()
        return added_count

    async def remove_member(
        self, conversation_id: str, user_id: str
    ) -> bool:
        """
        Remove member from conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID to remove

        Returns:
            True if removed, False if not found
        """
        result = await self.db.execute(
            delete(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id
                )
            )
        )
        await self.db.flush()
        return result.rowcount > 0

    async def update_role(
        self, conversation_id: str, user_id: str, role: ConversationRole
    ) -> Optional[ConversationMember]:
        """
        Update member role.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            role: New role

        Returns:
            Updated member or None
        """
        member = await self.get_member(conversation_id, user_id)
        if not member:
            return None

        member.role = role
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def update_last_read(
        self, conversation_id: str, user_id: str
    ) -> Optional[ConversationMember]:
        """
        Update last_read_at timestamp.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Updated member or None
        """
        member = await self.get_member(conversation_id, user_id)
        if not member:
            return None

        member.last_read_at = utc_now()
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def update_mute_settings(
        self,
        conversation_id: str,
        user_id: str,
        is_muted: bool,
        mute_until: Optional[datetime] = None
    ) -> Optional[ConversationMember]:
        """
        Update mute settings for member.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            is_muted: Whether to mute
            mute_until: Optional mute expiration

        Returns:
            Updated member or None
        """
        member = await self.get_member(conversation_id, user_id)
        if not member:
            return None

        member.is_muted = is_muted
        member.mute_until = mute_until
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def get_unread_counts_batch(
        self, user_id: str, members_by_conv: dict[str, "ConversationMember"]
    ) -> dict[str, int]:
        """
        Get unread message counts for multiple conversations in one query.

        Messenger pattern: fetch (conversation_id, created_at) for all candidate
        messages from others in a single query, then apply each conversation's
        last_read_at cutoff in Python — one DB round-trip, no dynamic SQL.

        Args:
            user_id: Current user UUID
            members_by_conv: Dict mapping conversation_id → ConversationMember
                             (already loaded via selectinload on conversation.members)

        Returns:
            Dict mapping conversation_id → unread count (0 if no unread)
        """
        if not members_by_conv:
            return {}

        conv_ids = list(members_by_conv.keys())

        # One query: all non-deleted messages from other users in these conversations
        query = (
            select(Message.conversation_id, Message.created_at)
            .where(
                and_(
                    Message.conversation_id.in_(conv_ids),
                    Message.sender_id != user_id,
                    Message.deleted_at.is_(None),
                )
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Apply each conversation's last_read_at cutoff in Python
        counts: dict[str, int] = {conv_id: 0 for conv_id in conv_ids}
        for conv_id, created_at in rows:
            member = members_by_conv.get(conv_id)
            if member is None:
                continue
            last_read_at = member.last_read_at
            if last_read_at is None or created_at > last_read_at:
                counts[conv_id] += 1

        return counts

    async def get_unread_count(
        self, conversation_id: str, user_id: str
    ) -> int:
        """
        Get unread message count for user in conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Number of unread messages
        """
        member = await self.get_member(conversation_id, user_id)
        if not member:
            return 0

        query = select(func.count()).select_from(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.deleted_at.is_(None)
            )
        )

        if member.last_read_at:
            query = query.where(Message.created_at > member.last_read_at)

        result = await self.db.execute(query)
        return result.scalar() or 0
