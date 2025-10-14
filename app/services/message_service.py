"""
Message service containing business logic for messaging operations.
Handles message CRUD, reactions, status updates, and integrations.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageType, MessageStatusType
from app.models.conversation import Conversation, ConversationMember
from app.repositories.message_repo import (
    MessageRepository,
    MessageStatusRepository,
    MessageReactionRepository
)
from app.core.tms_client import tms_client, TMSAPIException
from app.core.cache import cache
# from app.core.websocket import connection_manager
from sqlalchemy import select


class MessageService:
    """Service for message operations with business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize message service.

        Args:
            db: Database session
        """
        self.db = db
        self.message_repo = MessageRepository(db)
        self.status_repo = MessageStatusRepository(db)
        self.reaction_repo = MessageReactionRepository(db)
        # self.ws_manager = connection_manager

    async def _verify_conversation_membership(
        self,
        conversation_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Verify user is a member of the conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            True if user is member
        """
        result = await self.db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def _check_user_blocked(
        self,
        sender_id: UUID,
        recipient_id: UUID
    ) -> bool:
        """
        Check if sender is blocked by recipient.

        Args:
            sender_id: Sender user UUID
            recipient_id: Recipient user UUID

        Returns:
            True if blocked
        """
        from app.models.user_block import UserBlock

        result = await self.db.execute(
            select(UserBlock).where(
                UserBlock.blocker_id == recipient_id,
                UserBlock.blocked_id == sender_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def _update_conversation_timestamp(self, conversation_id: UUID) -> None:
        """
        Update conversation's updated_at timestamp.

        Args:
            conversation_id: Conversation UUID
        """
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            conversation.updated_at = datetime.utcnow()
            await self.db.flush()

    async def _enrich_message_with_user_data(
        self,
        message: Message
    ) -> Dict[str, Any]:
        """
        Enrich message with TMS user data.

        Args:
            message: Message instance

        Returns:
            Message dict with enriched user data
        """
        message_dict = {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "type": message.type,
            "metadata_json": message.metadata_json,
            "reply_to_id": message.reply_to_id,
            "is_edited": message.is_edited,
            "created_at": message.created_at,
            "updated_at": message.updated_at,
            "deleted_at": message.deleted_at,
            "reactions": [
                {
                    "id": r.id,
                    "message_id": r.message_id,
                    "user_id": r.user_id,
                    "emoji": r.emoji,
                    "created_at": r.created_at
                }
                for r in message.reactions
            ],
            "statuses": [
                {
                    "message_id": s.message_id,
                    "user_id": s.user_id,
                    "status": s.status,
                    "timestamp": s.timestamp
                }
                for s in message.statuses
            ]
        }

        # Fetch sender data from TMS
        if message.sender:
            try:
                sender_data = await tms_client.get_user(
                    message.sender.tms_user_id,
                    use_cache=True
                )
                message_dict["sender"] = sender_data
            except TMSAPIException:
                # Fallback to basic sender info
                message_dict["sender"] = {
                    "id": str(message.sender.id),
                    "tms_user_id": message.sender.tms_user_id
                }

        # Enrich reply_to if present
        if message.reply_to:
            message_dict["reply_to"] = await self._enrich_message_with_user_data(
                message.reply_to
            )

        return message_dict

    async def send_message(
        self,
        sender_id: UUID,
        conversation_id: UUID,
        content: Optional[str],
        message_type: MessageType = MessageType.TEXT,
        metadata_json: Dict[str, Any] = None,
        reply_to_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Send a new message.

        Args:
            sender_id: Sender user UUID
            conversation_id: Conversation UUID
            content: Message content
            message_type: Type of message
            metadata_json: Message metadata
            reply_to_id: ID of message being replied to

        Returns:
            Created message with enriched data

        Raises:
            HTTPException: If validation fails
        """
        # Verify sender is conversation member
        if not await self._verify_conversation_membership(conversation_id, sender_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Validate reply_to message if provided
        if reply_to_id:
            parent_message = await self.message_repo.get(reply_to_id)
            if not parent_message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent message not found"
                )
            if parent_message.conversation_id != conversation_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent message is from different conversation"
                )

        # Create message
        message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            type=message_type,
            metadata_json=metadata_json or {},
            reply_to_id=reply_to_id
        )

        # Get conversation members for status tracking
        result = await self.db.execute(
            select(ConversationMember)
            .where(ConversationMember.conversation_id == conversation_id)
        )
        members = result.scalars().all()

        # Create message statuses for all members
        for member in members:
            if member.user_id == sender_id:
                # Sender: mark as read immediately
                await self.status_repo.upsert_status(
                    message.id,
                    member.user_id,
                    MessageStatusType.READ
                )
            else:
                # Check if user is blocked
                is_blocked = await self._check_user_blocked(sender_id, member.user_id)
                if not is_blocked:
                    # Recipients: mark as sent
                    await self.status_repo.upsert_status(
                        message.id,
                        member.user_id,
                        MessageStatusType.SENT
                    )

        # Update conversation timestamp
        await self._update_conversation_timestamp(conversation_id)

        # Commit transaction
        await self.db.commit()

        # Reload message with relations
        message = await self.message_repo.get_with_relations(message.id)

        # Enrich with TMS user data
        enriched_message = await self._enrich_message_with_user_data(message)

        # Broadcast new message via WebSocket
        await self.ws_manager.broadcast_new_message(
            conversation_id,
            enriched_message
        )

        return enriched_message

    async def get_message(self, message_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """
        Get a single message by ID.

        Args:
            message_id: Message UUID
            user_id: Requesting user UUID

        Returns:
            Message with enriched data

        Raises:
            HTTPException: If not found or no access
        """
        message = await self.message_repo.get_with_relations(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        # Verify user has access to conversation
        if not await self._verify_conversation_membership(
            message.conversation_id,
            user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this message"
            )

        return await self._enrich_message_with_user_data(message)

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int = 50,
        cursor: Optional[UUID] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[UUID], bool]:
        """
        Get messages for a conversation with pagination.

        Args:
            conversation_id: Conversation UUID
            user_id: Requesting user UUID
            limit: Number of messages
            cursor: Cursor for pagination

        Returns:
            Tuple of (enriched messages, next_cursor, has_more)

        Raises:
            HTTPException: If no access
        """
        # Verify user is conversation member
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Get messages
        messages, next_cursor, has_more = await self.message_repo.get_conversation_messages(
            conversation_id,
            limit,
            cursor
        )

        # Enrich messages with TMS user data
        enriched_messages = []
        for message in messages:
            enriched_messages.append(
                await self._enrich_message_with_user_data(message)
            )

        return enriched_messages, next_cursor, has_more

    async def edit_message(
        self,
        message_id: UUID,
        user_id: UUID,
        new_content: str
    ) -> Dict[str, Any]:
        """
        Edit a message.

        Args:
            message_id: Message UUID
            user_id: User UUID (must be sender)
            new_content: New message content

        Returns:
            Updated message

        Raises:
            HTTPException: If not found or no permission
        """
        message = await self.message_repo.get(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own messages"
            )

        if message.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot edit deleted message"
            )

        # Update message
        updated_message = await self.message_repo.update(
            message_id,
            content=new_content,
            is_edited=True,
            updated_at=datetime.utcnow()
        )

        await self.db.commit()

        # Reload with relations and enrich
        updated_message = await self.message_repo.get_with_relations(message_id)
        enriched_message = await self._enrich_message_with_user_data(updated_message)

        # Broadcast message edit via WebSocket
        await self.ws_manager.broadcast_message_edited(
            message.conversation_id,
            enriched_message
        )

        return enriched_message

    async def delete_message(
        self,
        message_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Delete a message (soft delete).

        Args:
            message_id: Message UUID
            user_id: User UUID (must be sender)

        Returns:
            Success response with deleted_at timestamp

        Raises:
            HTTPException: If not found or no permission
        """
        message = await self.message_repo.get(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own messages"
            )

        if message.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message already deleted"
            )

        # Soft delete
        deleted_message = await self.message_repo.soft_delete(message_id)
        await self.db.commit()

        # Broadcast message deletion via WebSocket
        await self.ws_manager.broadcast_message_deleted(
            message.conversation_id,
            message_id
        )

        return {
            "success": True,
            "message": "Message deleted successfully",
            "deleted_at": deleted_message.deleted_at
        }

    async def add_reaction(
        self,
        message_id: UUID,
        user_id: UUID,
        emoji: str
    ) -> Dict[str, Any]:
        """
        Add a reaction to a message.

        Args:
            message_id: Message UUID
            user_id: User UUID
            emoji: Emoji string

        Returns:
            Created reaction

        Raises:
            HTTPException: If message not found or already reacted
        """
        message = await self.message_repo.get(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        # Verify user has access
        if not await self._verify_conversation_membership(
            message.conversation_id,
            user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this message"
            )

        reaction = await self.reaction_repo.add_reaction(message_id, user_id, emoji)

        if not reaction:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already reacted with this emoji"
            )

        await self.db.commit()

        reaction_data = {
            "id": reaction.id,
            "message_id": reaction.message_id,
            "user_id": reaction.user_id,
            "emoji": reaction.emoji,
            "created_at": reaction.created_at
        }

        # Broadcast reaction added via WebSocket
        await self.ws_manager.broadcast_reaction_added(
            message.conversation_id,
            message_id,
            reaction_data
        )

        return reaction_data

    async def remove_reaction(
        self,
        message_id: UUID,
        user_id: UUID,
        emoji: str
    ) -> Dict[str, Any]:
        """
        Remove a reaction from a message.

        Args:
            message_id: Message UUID
            user_id: User UUID
            emoji: Emoji string

        Returns:
            Success response

        Raises:
            HTTPException: If reaction not found
        """
        # Get message for conversation_id
        message = await self.message_repo.get(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        removed = await self.reaction_repo.remove_reaction(message_id, user_id, emoji)

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reaction not found"
            )

        await self.db.commit()

        # Broadcast reaction removed via WebSocket
        await self.ws_manager.broadcast_reaction_removed(
            message.conversation_id,
            message_id,
            user_id,
            emoji
        )

        return {
            "success": True,
            "message": "Reaction removed successfully"
        }

    async def mark_messages_read(
        self,
        message_ids: List[UUID],
        user_id: UUID,
        conversation_id: UUID
    ) -> Dict[str, Any]:
        """
        Mark multiple messages as read.

        Args:
            message_ids: List of message UUIDs
            user_id: User UUID
            conversation_id: Conversation UUID

        Returns:
            Success response with count

        Raises:
            HTTPException: If no access
        """
        # Verify user is conversation member
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Mark messages as read
        count = await self.status_repo.mark_messages_as_read(message_ids, user_id)
        await self.db.commit()

        # Broadcast message status updates via WebSocket
        for message_id in message_ids:
            await self.ws_manager.broadcast_message_status(
                conversation_id,
                message_id,
                user_id,
                MessageStatusType.READ.value
            )

        return {
            "success": True,
            "updated_count": count,
            "message": f"Marked {count} messages as read"
        }

    async def search_messages(
        self,
        query: str,
        user_id: UUID,
        conversation_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search messages with filters.

        Args:
            query: Search query
            user_id: Requesting user UUID
            conversation_id: Optional conversation filter
            sender_id: Optional sender filter
            start_date: Optional start date
            end_date: Optional end date
            limit: Max results

        Returns:
            List of enriched messages

        Raises:
            HTTPException: If no access to conversation
        """
        # If conversation filter is provided, verify access
        if conversation_id:
            if not await self._verify_conversation_membership(conversation_id, user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this conversation"
                )

        # Search messages
        messages = await self.message_repo.search_messages(
            query,
            conversation_id,
            sender_id,
            start_date,
            end_date,
            limit
        )

        # Enrich messages
        enriched_messages = []
        for message in messages:
            # Verify user has access to each message's conversation
            if await self._verify_conversation_membership(
                message.conversation_id,
                user_id
            ):
                enriched_messages.append(
                    await self._enrich_message_with_user_data(message)
                )

        return enriched_messages
