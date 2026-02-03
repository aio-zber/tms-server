"""
Notification service for business logic.
Handles notification preferences and muted conversations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, time as Time
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.notification_preferences import NotificationPreferences
from app.models.muted_conversation import MutedConversation
from app.models.user import User
from app.repositories.notification_repo import (
    NotificationPreferencesRepository,
    MutedConversationRepository
)
from app.schemas.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    MutedConversationResponse,
    MutedConversationListResponse
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for notification-related business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize notification service."""
        self.db = db
        self.preferences_repo = NotificationPreferencesRepository(db)
        self.muted_repo = MutedConversationRepository(db)

    async def get_or_create_preferences(self, user_id: str) -> NotificationPreferencesResponse:
        """
        Get user's notification preferences, creating defaults if not exists.

        Args:
            user_id: User ID

        Returns:
            NotificationPreferencesResponse
        """
        # Try to get existing preferences using repository
        preferences = await self.preferences_repo.get_by_user_id(user_id)

        # Create defaults if not exists
        if not preferences:
            preferences = await self.preferences_repo.create(
                user_id=user_id,
                sound_enabled=True,
                sound_volume=75,
                browser_notifications_enabled=False,
                enable_message_notifications=True,
                enable_mention_notifications=True,
                enable_reaction_notifications=True,
                enable_member_activity_notifications=False,
                dnd_enabled=False,
                dnd_start=None,
                dnd_end=None
            )
            logger.info(f"Created default notification preferences for user {user_id}")

        # Convert to response format (handle Time objects)
        response_dict = {
            'id': str(preferences.id),
            'user_id': str(preferences.user_id),
            'sound_enabled': preferences.sound_enabled,
            'sound_volume': preferences.sound_volume,
            'browser_notifications_enabled': preferences.browser_notifications_enabled,
            'enable_message_notifications': preferences.enable_message_notifications,
            'enable_mention_notifications': preferences.enable_mention_notifications,
            'enable_reaction_notifications': preferences.enable_reaction_notifications,
            'enable_member_activity_notifications': preferences.enable_member_activity_notifications,
            'dnd_enabled': preferences.dnd_enabled,
            'dnd_start': preferences.dnd_start.strftime('%H:%M') if preferences.dnd_start else None,
            'dnd_end': preferences.dnd_end.strftime('%H:%M') if preferences.dnd_end else None,
            'created_at': preferences.created_at,
            'updated_at': preferences.updated_at
        }

        return NotificationPreferencesResponse.model_validate(response_dict)

    async def update_preferences(
        self,
        user_id: str,
        updates: NotificationPreferencesUpdate
    ) -> NotificationPreferencesResponse:
        """
        Update user's notification preferences.

        Args:
            user_id: User ID
            updates: Preference updates

        Returns:
            Updated NotificationPreferencesResponse
        """
        # Get or create preferences using repository
        preferences = await self.preferences_repo.get_by_user_id(user_id)

        # Apply updates (only update fields that are provided)
        update_data = updates.model_dump(exclude_unset=True)

        # Convert time strings to Python time objects for database
        if 'dnd_start' in update_data and update_data['dnd_start'] is not None:
            update_data['dnd_start'] = Time.fromisoformat(update_data['dnd_start'])
        if 'dnd_end' in update_data and update_data['dnd_end'] is not None:
            update_data['dnd_end'] = Time.fromisoformat(update_data['dnd_end'])

        if not preferences:
            # Create new with provided values
            preferences = await self.preferences_repo.create(
                user_id=user_id,
                **update_data
            )
            logger.info(f"Created notification preferences for user {user_id}")
        else:
            # Update existing
            for key, value in update_data.items():
                setattr(preferences, key, value)

            await self.db.commit()
            await self.db.refresh(preferences)
            logger.info(f"Updated notification preferences for user {user_id}")

        # Convert time objects back to strings for response
        response_dict = {
            'id': str(preferences.id),
            'user_id': str(preferences.user_id),
            'sound_enabled': preferences.sound_enabled,
            'sound_volume': preferences.sound_volume,
            'browser_notifications_enabled': preferences.browser_notifications_enabled,
            'enable_message_notifications': preferences.enable_message_notifications,
            'enable_mention_notifications': preferences.enable_mention_notifications,
            'enable_reaction_notifications': preferences.enable_reaction_notifications,
            'enable_member_activity_notifications': preferences.enable_member_activity_notifications,
            'dnd_enabled': preferences.dnd_enabled,
            'dnd_start': preferences.dnd_start.strftime('%H:%M') if preferences.dnd_start else None,
            'dnd_end': preferences.dnd_end.strftime('%H:%M') if preferences.dnd_end else None,
            'created_at': preferences.created_at,
            'updated_at': preferences.updated_at
        }

        return NotificationPreferencesResponse.model_validate(response_dict)

    async def mute_conversation(
        self,
        user_id: str,
        conversation_id: str
    ) -> MutedConversationResponse:
        """
        Mute a conversation for a user.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            MutedConversationResponse
        """
        # Check if already muted using repository
        existing = await self.muted_repo.get_mute(user_id, conversation_id)

        if existing:
            # Already muted, return existing
            return MutedConversationResponse.model_validate(existing)

        # Create new muted conversation using repository
        muted = await self.muted_repo.create(
            user_id=user_id,
            conversation_id=conversation_id
        )

        logger.info(f"User {user_id} muted conversation {conversation_id}")

        return MutedConversationResponse.model_validate(muted)

    async def unmute_conversation(
        self,
        user_id: str,
        conversation_id: str
    ) -> bool:
        """
        Unmute a conversation for a user.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            True if unmuted, False if wasn't muted
        """
        stmt = select(MutedConversation).where(
            and_(
                MutedConversation.user_id == user_id,
                MutedConversation.conversation_id == conversation_id
            )
        )
        result = await self.db.execute(stmt)
        muted = result.scalar_one_or_none()

        if not muted:
            return False

        await self.db.delete(muted)
        await self.db.commit()

        logger.info(f"User {user_id} unmuted conversation {conversation_id}")

        return True

    async def get_muted_conversations(self, user_id: str) -> MutedConversationListResponse:
        """
        Get all muted conversations for a user.

        Args:
            user_id: User ID

        Returns:
            MutedConversationListResponse
        """
        # Get all muted conversations using repository
        muted_convos = await self.muted_repo.get_user_mutes(user_id)

        return MutedConversationListResponse(
            muted_conversations=[
                MutedConversationResponse.model_validate(mc)
                for mc in muted_convos
            ],
            total=len(muted_convos)
        )
