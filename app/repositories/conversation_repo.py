"""
Conversation repository for database operations.
Handles conversations, members, and related queries.
"""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, delete, literal, case
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
        self, conversation_id: UUID, include_members: bool = True
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
        user_id: UUID,
        limit: int = 50,
        cursor: Optional[UUID] = None
    ) -> Tuple[List[Conversation], Optional[UUID], bool]:
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
        creator_id: UUID,
        member_ids: List[UUID],
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Conversation:
        """
        Create conversation with members in a single transaction.

        Args:
            type: Conversation type (dm/group)
            creator_id: Creator user ID
            member_ids: List of member user IDs (excluding creator)
            name: Optional conversation name
            avatar_url: Optional avatar URL

        Returns:
            Created conversation with members
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
            last_read_at=datetime.utcnow()
        )
        self.db.add(creator_member)

        # Add other members
        for member_id in member_ids:
            if member_id != creator_id:  # Avoid duplicate
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
        self, user1_id: UUID, user2_id: UUID
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
        conversation_id: UUID,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Optional[Conversation]:
        """
        Update conversation details.

        Args:
            conversation_id: Conversation UUID
            name: Updated name
            avatar_url: Updated avatar URL

        Returns:
            Updated conversation or None
        """
        updates = {}
        if name is not None:
            updates['name'] = name
        if avatar_url is not None:
            updates['avatar_url'] = avatar_url

        if updates:
            updates['updated_at'] = datetime.utcnow()
            return await self.update(conversation_id, **updates)

        return await self.get_with_relations(conversation_id)

    async def get_last_message(self, conversation_id: UUID) -> Optional[Message]:
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

    async def search_conversations(
        self,
        user_id: UUID,
        query: str,
        limit: int = 20
    ) -> List[Conversation]:
        """
        Search conversations by name, description, or member names using PostgreSQL full-text search.

        Implements hybrid search strategy similar to Telegram/Messenger:
        - Uses trigram similarity for fuzzy matching
        - Searches conversation name (60% weight)
        - Searches member names (40% weight)
        - Only returns conversations the user is a member of

        Args:
            user_id: User UUID (must be a member of returned conversations)
            query: Search query string
            limit: Maximum results to return (default 20)

        Returns:
            List of conversations ordered by relevance score
        """
        # Normalize search query for trigram matching
        search_term = query.strip().lower()

        # Subquery to get user's conversation IDs
        member_subquery = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
        )

        # Alias for member users to search
        MemberUser = aliased(User)

        # Build search query with weighted scoring
        # Using ILIKE for simple matching and similarity for ranking
        stmt = (
            select(
                Conversation,
                # Calculate relevance score
                case(
                    # Exact match on conversation name (highest priority)
                    (func.lower(Conversation.name).like(f"%{search_term}%"), literal(1.0)),
                    # Fuzzy match on conversation name using similarity
                    else_=(
                        func.coalesce(
                            func.similarity(func.lower(Conversation.name), search_term) * 0.6,
                            literal(0.0)
                        ) +
                        # Add member name similarity score
                        func.coalesce(
                            func.max(
                                func.similarity(
                                    func.lower(
                                        func.concat(MemberUser.first_name, ' ', MemberUser.last_name)
                                    ),
                                    search_term
                                )
                            ) * 0.4,
                            literal(0.0)
                        )
                    )
                ).label("relevance")
            )
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
                        # Conversation name match
                        func.lower(Conversation.name).like(f"%{search_term}%"),
                        # Member name match (first name or last name)
                        func.lower(
                            func.concat(MemberUser.first_name, ' ', MemberUser.last_name)
                        ).like(f"%{search_term}%"),
                        # Trigram similarity threshold (0.3 is a good balance)
                        func.similarity(func.lower(Conversation.name), search_term) > 0.3,
                        func.similarity(
                            func.lower(
                                func.concat(MemberUser.first_name, ' ', MemberUser.last_name)
                            ),
                            search_term
                        ) > 0.3
                    )
                )
            )
            .group_by(Conversation.id)
            .order_by(desc(literal_column("relevance")), desc(Conversation.updated_at))
            .limit(limit)
            .options(
                selectinload(Conversation.members).selectinload(ConversationMember.user),
                selectinload(Conversation.creator)
            )
        )

        result = await self.db.execute(stmt)
        # Extract just the Conversation objects (first element of each tuple)
        conversations = [row[0] for row in result.all()]
        return conversations


class ConversationMemberRepository:
    """Repository for conversation member operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(
        self, conversation_id: UUID, user_id: UUID
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

    async def is_member(self, conversation_id: UUID, user_id: UUID) -> bool:
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

    async def is_admin(self, conversation_id: UUID, user_id: UUID) -> bool:
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
        self, conversation_id: UUID
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

    async def get_member_count(self, conversation_id: UUID) -> int:
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
        self, conversation_id: UUID, user_ids: List[UUID]
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
        self, conversation_id: UUID, user_id: UUID
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
        self, conversation_id: UUID, user_id: UUID, role: ConversationRole
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
        self, conversation_id: UUID, user_id: UUID
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

        member.last_read_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def update_mute_settings(
        self,
        conversation_id: UUID,
        user_id: UUID,
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

    async def get_unread_count(
        self, conversation_id: UUID, user_id: UUID
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

        # Count messages after last_read_at
        query = select(func.count()).select_from(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,  # Exclude own messages
                Message.deleted_at.is_(None)
            )
        )

        if member.last_read_at:
            query = query.where(Message.created_at > member.last_read_at)

        result = await self.db.execute(query)
        return result.scalar()
