"""
System Message Service

Creates and broadcasts system messages for conversation events.
Follows Messenger's pattern: system messages are persisted in the database
and broadcasted via the same 'message:new' event as regular messages.

Security:
- Server-side validation ensures only authorized actions create system messages
- Message content is server-controlled (prevents client-side spoofing)
- Audit trail maintained via database persistence
"""
from datetime import datetime
from typing import Dict, List, Any
# UUID import removed - using str for ID types

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageType
from app.models.user import User


class SystemMessageService:
    """Service for creating system messages for conversation events."""

    @staticmethod
    def _get_user_display_name(user: User) -> str:
        """
        Get display name for a user.

        Priority: first_name + last_name > username > email
        """
        if user.first_name or user.last_name:
            parts = [p for p in [user.first_name, user.last_name] if p]
            return ' '.join(parts)
        return user.username or user.email or "Someone"

    @staticmethod
    async def create_member_added_message(
        db: AsyncSession,
        conversation_id: str,
        actor: User,
        added_members: List[Dict[str, Any]]
    ) -> Message:
        """
        Create system message when members are added to a conversation.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            actor: User who added the members
            added_members: List of added member dicts with 'id' and 'full_name'

        Returns:
            Created Message object
        """
        member_names = [m['full_name'] for m in added_members]
        member_ids = [str(m['id']) for m in added_members]

        actor_name = SystemMessageService._get_user_display_name(actor)

        # Generate human-readable content
        if len(member_names) == 1:
            content = f"{actor_name} added {member_names[0]} to the group"
        else:
            names_str = ', '.join(member_names)
            content = f"{actor_name} added {names_str} to the group"

        # Create metadata with event details
        metadata = {
            'system': {
                'eventType': 'member_added',
                'actorId': str(actor.id),
                'actorName': actor_name,
                'addedMemberIds': member_ids,
                'addedMemberNames': member_names
            }
        }

        return await SystemMessageService._create_system_message(
            db=db,
            conversation_id=conversation_id,
            sender_id=actor.id,
            content=content,
            metadata=metadata
        )

    @staticmethod
    async def create_member_removed_message(
        db: AsyncSession,
        conversation_id: str,
        actor: User,
        removed_user: User
    ) -> Message:
        """
        Create system message when a member is removed from a conversation.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            actor: User who removed the member
            removed_user: User who was removed

        Returns:
            Created Message object
        """
        actor_name = SystemMessageService._get_user_display_name(actor)
        removed_name = SystemMessageService._get_user_display_name(removed_user)

        content = f"{actor_name} removed {removed_name}"

        metadata = {
            'system': {
                'eventType': 'member_removed',
                'actorId': str(actor.id),
                'actorName': actor_name,
                'targetUserId': str(removed_user.id),
                'targetUserName': removed_name
            }
        }

        return await SystemMessageService._create_system_message(
            db=db,
            conversation_id=conversation_id,
            sender_id=actor.id,
            content=content,
            metadata=metadata
        )

    @staticmethod
    async def create_member_left_message(
        db: AsyncSession,
        conversation_id: str,
        user: User
    ) -> Message:
        """
        Create system message when a member leaves a conversation.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            user: User who left the conversation

        Returns:
            Created Message object
        """
        user_name = SystemMessageService._get_user_display_name(user)

        content = f"{user_name} left the group"

        metadata = {
            'system': {
                'eventType': 'member_left',
                'actorId': str(user.id),
                'actorName': user_name
            }
        }

        return await SystemMessageService._create_system_message(
            db=db,
            conversation_id=conversation_id,
            sender_id=user.id,
            content=content,
            metadata=metadata
        )

    @staticmethod
    async def create_conversation_updated_message(
        db: AsyncSession,
        conversation_id: str,
        actor: User,
        updates: Dict[str, Any]
    ) -> Message:
        """
        Create system message when conversation details are updated.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            actor: User who updated the conversation
            updates: Dict with 'name' and/or 'avatar_url' keys

        Returns:
            Created Message object
        """
        actor_name = SystemMessageService._get_user_display_name(actor)

        # Generate content based on what was updated
        if 'name' in updates and updates['name']:
            content = f'{actor_name} changed the group name to "{updates["name"]}"'
        elif 'avatar_url' in updates and updates['avatar_url']:
            content = f"{actor_name} changed the group photo"
        else:
            content = f"{actor_name} updated the group"

        metadata = {
            'system': {
                'eventType': 'conversation_updated',
                'actorId': str(actor.id),
                'actorName': actor_name,
                'details': updates
            }
        }

        return await SystemMessageService._create_system_message(
            db=db,
            conversation_id=conversation_id,
            sender_id=actor.id,
            content=content,
            metadata=metadata
        )

    @staticmethod
    async def create_message_deleted_message(
        db: AsyncSession,
        conversation_id: str,
        actor: User
    ) -> Message:
        """
        Create system message when a message is deleted for everyone.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            actor: User who deleted the message

        Returns:
            Created Message object
        """
        actor_name = SystemMessageService._get_user_display_name(actor)

        content = f"{actor_name} deleted a message"

        metadata = {
            'system': {
                'eventType': 'message_deleted',
                'actorId': str(actor.id),
                'actorName': actor_name
            }
        }

        return await SystemMessageService._create_system_message(
            db=db,
            conversation_id=conversation_id,
            sender_id=actor.id,
            content=content,
            metadata=metadata
        )

    @staticmethod
    async def _create_system_message(
        db: AsyncSession,
        conversation_id: str,
        sender_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> Message:
        """
        Internal helper to create and persist a system message.

        Args:
            db: Database session
            conversation_id: Target conversation ID
            sender_id: ID of the user who triggered the event
            content: Human-readable message content
            metadata: Event metadata dict

        Returns:
            Created Message object
        """
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            type=MessageType.SYSTEM,
            metadata_json=metadata,
            is_edited=False,
            created_at=datetime.utcnow()
        )

        db.add(message)
        await db.commit()
        await db.refresh(message)

        return message
