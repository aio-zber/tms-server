"""
Notification repository for database operations.
Handles CRUD operations for notification preferences and muted conversations.
"""
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_preferences import NotificationPreferences
from app.models.muted_conversation import MutedConversation
from app.repositories.base import BaseRepository


class NotificationPreferencesRepository(BaseRepository[NotificationPreferences]):
    """Repository for notification preferences database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize notification preferences repository."""
        super().__init__(NotificationPreferences, db)

    async def get_by_user_id(self, user_id: str) -> Optional[NotificationPreferences]:
        """
        Get notification preferences by user ID.

        Args:
            user_id: User ID to get preferences for

        Returns:
            NotificationPreferences or None if not found
        """
        result = await self.db.execute(
            select(NotificationPreferences).where(
                NotificationPreferences.user_id == user_id
            )
        )
        return result.scalar_one_or_none()


class MutedConversationRepository(BaseRepository[MutedConversation]):
    """Repository for muted conversation database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize muted conversation repository."""
        super().__init__(MutedConversation, db)

    async def get_mute(
        self,
        user_id: str,
        conversation_id: str
    ) -> Optional[MutedConversation]:
        """
        Get mute record for user and conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            MutedConversation or None if not muted
        """
        result = await self.db.execute(
            select(MutedConversation).where(
                and_(
                    MutedConversation.user_id == user_id,
                    MutedConversation.conversation_id == conversation_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_mutes(self, user_id: str) -> List[MutedConversation]:
        """
        Get all muted conversations for a user.

        Args:
            user_id: User ID

        Returns:
            List of muted conversations
        """
        result = await self.db.execute(
            select(MutedConversation).where(
                MutedConversation.user_id == user_id
            )
        )
        return result.scalars().all()
