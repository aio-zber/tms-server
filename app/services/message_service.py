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
from app.core.cache import (
    cache,
    get_cached_user_data,
    invalidate_unread_count_cache,
    invalidate_total_unread_count_cache
)
from app.core.websocket import connection_manager
from sqlalchemy import select, inspect
from sqlalchemy.orm import object_session


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
        self.ws_manager = connection_manager

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
        # Check if sender is loaded (not lazy) to avoid greenlet_spawn error
        sender_loaded = False
        sender_tms_id = None

        # Safely check if sender is loaded without triggering lazy load
        try:
            insp = inspect(message)
            if 'sender' not in insp.unloaded:
                sender_loaded = True
                if message.sender:
                    sender_tms_id = message.sender.tms_user_id
        except Exception:
            # If inspection fails, try direct access (might be already loaded)
            try:
                if message.sender:
                    sender_loaded = True
                    sender_tms_id = message.sender.tms_user_id
            except Exception:
                pass

        if sender_loaded and sender_tms_id:
            try:
                sender_data = await tms_client.get_user(
                    sender_tms_id,
                    use_cache=True
                )
                message_dict["sender"] = sender_data
            except TMSAPIException:
                # Fallback to basic sender info
                message_dict["sender"] = {
                    "id": str(message.sender_id),
                    "tms_user_id": sender_tms_id
                }
        else:
            # Sender not loaded, use minimal info
            message_dict["sender"] = {
                "id": str(message.sender_id)
            }

        # Enrich reply_to if present
        if message.reply_to_id:
            print(f"[ENRICH] Message {message.id} has reply_to_id: {message.reply_to_id}")

            # Check if reply_to is loaded without triggering lazy load
            reply_to_loaded = False
            try:
                insp = inspect(message)
                if 'reply_to' not in insp.unloaded and message.reply_to is not None:
                    reply_to_loaded = True
                    print(f"[ENRICH] reply_to object loaded: True")
            except Exception:
                # If inspection fails, try direct access carefully
                try:
                    if message.reply_to is not None:
                        reply_to_loaded = True
                        print(f"[ENRICH] reply_to object loaded via direct access: True")
                except Exception:
                    print(f"[ENRICH] ⚠️ reply_to not loaded, cannot access without triggering lazy load")

            if reply_to_loaded:
                try:
                    print(f"[ENRICH] Recursively enriching reply_to message: {message.reply_to.id}")
                    message_dict["reply_to"] = await self._enrich_message_with_user_data(
                        message.reply_to
                    )
                except Exception as e:
                    print(f"[MESSAGE_SERVICE] ❌ Failed to enrich reply_to: {e}")
                    # Fallback: return ALL required fields for MessageResponse schema
                    try:
                        message_dict["reply_to"] = {
                            "id": message.reply_to.id,
                            "conversation_id": message.reply_to.conversation_id,
                            "sender_id": message.reply_to.sender_id,
                            "content": message.reply_to.content,
                            "type": message.reply_to.type,
                            "metadata_json": message.reply_to.metadata_json or {},
                            "reply_to_id": message.reply_to.reply_to_id,
                            "is_edited": message.reply_to.is_edited,
                            "created_at": message.reply_to.created_at,
                            "updated_at": message.reply_to.updated_at,
                            "deleted_at": message.reply_to.deleted_at,
                            "reactions": [],
                            "statuses": [],
                            "sender": None,
                            "reply_to": None
                        }
                    except Exception as fallback_error:
                        print(f"[MESSAGE_SERVICE] ❌ Even fallback failed: {fallback_error}")
                        # If even basic access fails, set to None
                        message_dict["reply_to"] = None
            else:
                print(f"[ENRICH] ⚠️ WARNING: reply_to_id exists but reply_to object is not loaded! Setting to None.")
                message_dict["reply_to"] = None
        else:
            # Explicitly set to None if no reply_to_id
            message_dict["reply_to"] = None

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
            print(f"[MESSAGE_SERVICE] 🔗 Validating reply_to_id: {reply_to_id}")
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
            print(f"[MESSAGE_SERVICE] ✅ Reply validation passed for message {reply_to_id}")

        # Create message
        print(f"[MESSAGE_SERVICE] 📝 Creating message with reply_to_id: {reply_to_id}")
        message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            type=message_type,
            metadata_json=metadata_json or {},
            reply_to_id=reply_to_id
        )
        print(f"[MESSAGE_SERVICE] ✅ Message created: id={message.id}, content='{content}', reply_to_id={message.reply_to_id}")
        print(f"[MESSAGE_SERVICE] 📅 Message timestamps: created_at={message.created_at}, updated_at={message.updated_at}")
        print(f"[MESSAGE_SERVICE] 🗑️ Message deleted_at: {message.deleted_at}")
        print(f"[MESSAGE_SERVICE] 🔍 Message conversation_id: {message.conversation_id}")
        print(f"[MESSAGE_SERVICE] 🔍 Message sender_id: {message.sender_id}")
        
        # CRITICAL DEBUG: Check if created_at is in the past
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        time_diff = (now - message.created_at).total_seconds()
        print(f"[MESSAGE_SERVICE] ⏰ Time difference from now: {time_diff} seconds")
        if time_diff > 60:
            print(f"[MESSAGE_SERVICE] ⚠️⚠️⚠️ WARNING: Message created_at is {time_diff/3600:.2f} hours in the PAST!")

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
        print(f"[MESSAGE_SERVICE] ✅ Transaction committed for message {message.id}")

        # Invalidate unread count cache for all conversation members (except sender)
        # Following Messenger/Telegram pattern: new message = increment unread for recipients
        for member in members:
            if member.user_id != sender_id:
                await invalidate_unread_count_cache(str(member.user_id), str(conversation_id))
                await invalidate_total_unread_count_cache(str(member.user_id))
        print(f"[MESSAGE_SERVICE] 🗑️ Invalidated unread count cache for {len(members)-1} recipients")

        # Reload message with relations
        message = await self.message_repo.get_with_relations(message.id)
        print(f"[MESSAGE_SERVICE] 🔄 Message reloaded after commit: id={message.id}")
        print(f"[MESSAGE_SERVICE] 🔄 Reloaded timestamps: created_at={message.created_at}, updated_at={message.updated_at}, deleted_at={message.deleted_at}")

        # Enrich with TMS user data
        enriched_message = await self._enrich_message_with_user_data(message)

        # Convert UUIDs and datetimes to strings for JSON serialization
        def convert_to_json_serializable(obj):
            """Recursively convert UUID and datetime objects to strings for JSON serialization."""
            from datetime import datetime
            if isinstance(obj, dict):
                return {k: convert_to_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            elif isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        # Prepare message for WebSocket broadcast (all UUIDs and datetimes as strings)
        broadcast_message = convert_to_json_serializable(enriched_message)

        # Broadcast new message via WebSocket
        try:
            print(f"[MESSAGE_SERVICE] About to broadcast message: {message.id}")
            print(f"[MESSAGE_SERVICE] Conversation ID: {conversation_id}")
            print(f"[MESSAGE_SERVICE] WebSocket manager: {self.ws_manager}")
            
            await self.ws_manager.broadcast_new_message(
                conversation_id,
                broadcast_message
            )
            
            print(f"[MESSAGE_SERVICE] ✅ Broadcast completed for message: {message.id}")
        except Exception as broadcast_error:
            print(f"[MESSAGE_SERVICE] ❌ Broadcast failed: {type(broadcast_error).__name__}: {str(broadcast_error)}")
            import traceback
            print(traceback.format_exc())
            # Don't fail the message send if broadcast fails
            pass

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
        limit: int = 10,
        cursor: Optional[UUID] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[UUID], bool]:
        """
        Get messages for a conversation with pagination.
        OPTIMIZED: Uses batch fetching to avoid N+1 problem.

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
        print(f"[MESSAGE_SERVICE] 🚀 get_conversation_messages called for conversation: {conversation_id}, limit: {limit}")
        
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

        print(f"[MESSAGE_SERVICE] 📦 Fetched {len(messages)} messages from DB")
        
        if not messages:
            return [], next_cursor, has_more

        # OPTIMIZATION: Batch fetch all unique sender IDs in ONE API call
        # This fixes the N+1 query problem (50 messages = 1 API call instead of 50)
        sender_ids = list(set(
            msg.sender.tms_user_id
            for msg in messages
            if msg.sender and msg.sender.tms_user_id
        ))

        # Fetch all users at once
        users_map = {}
        if sender_ids:
            try:
                users = await tms_client.get_users(sender_ids)
                # Build lookup map (handle both "id" and "tms_user_id" fields)
                for user in users:
                    user_id_key = user.get("id") or user.get("tms_user_id")
                    if user_id_key:
                        users_map[user_id_key] = user
            except TMSAPIException as e:
                # Log error but continue - we'll use cached data or fallback
                print(f"Warning: Batch user fetch failed: {e}")

        # Enrich messages with pre-fetched user data
        print(f"[MESSAGE_SERVICE] 🔄 Starting message enrichment loop for {len(messages)} messages")
        
        # DEBUG: Count how many messages have reply_to_id vs reply_to loaded
        messages_with_reply_id = [m for m in messages if m.reply_to_id]
        messages_with_reply_loaded = [m for m in messages if m.reply_to]
        print(f"[MESSAGE_SERVICE] 📊 Messages with reply_to_id: {len(messages_with_reply_id)}")
        print(f"[MESSAGE_SERVICE] 📊 Messages with reply_to loaded: {len(messages_with_reply_loaded)}")
        if messages_with_reply_id:
            print(f"[MESSAGE_SERVICE] 📋 Message IDs with reply_to_id: {[str(m.id)[:8] for m in messages_with_reply_id]}")
        
        enriched_messages = []
        for message in messages:
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

            # Use pre-fetched user data
            if message.sender and message.sender.tms_user_id:
                sender_tms_id = message.sender.tms_user_id
                if sender_tms_id in users_map:
                    # Use batch-fetched data
                    message_dict["sender"] = users_map[sender_tms_id]
                else:
                    # Fallback: Try individual cache lookup
                    try:
                        cached = await get_cached_user_data(sender_tms_id)
                        if cached:
                            message_dict["sender"] = cached
                        else:
                            # Last resort: Basic sender info
                            message_dict["sender"] = {
                                "id": str(message.sender.id),
                                "tms_user_id": sender_tms_id
                            }
                    except Exception:
                        message_dict["sender"] = {
                            "id": str(message.sender.id),
                            "tms_user_id": sender_tms_id
                        }

            # Handle reply_to enrichment (recursive)
            if message.reply_to:
                print(f"[MESSAGE_SERVICE] ✅ Message {message.id} has reply_to: {message.reply_to.id}")
                # For replied messages, use individual enrichment
                # (these are typically 1-2 messages, not worth batch optimization)
                try:
                    message_dict["reply_to"] = await self._enrich_message_with_user_data(
                        message.reply_to
                    )
                    print(f"[MESSAGE_SERVICE] ✅ Successfully enriched reply_to for message {message.id}")
                except Exception as e:
                    print(f"[MESSAGE_SERVICE] ❌ Failed to enrich reply_to: {e}")
                    # Fallback: Include ALL required fields for MessageResponse schema
                    try:
                        message_dict["reply_to"] = {
                            "id": message.reply_to.id,
                            "conversation_id": message.reply_to.conversation_id,
                            "sender_id": message.reply_to.sender_id,
                            "content": message.reply_to.content,
                            "type": message.reply_to.type,
                            "metadata_json": message.reply_to.metadata_json or {},
                            "reply_to_id": message.reply_to.reply_to_id,
                            "is_edited": message.reply_to.is_edited,
                            "created_at": message.reply_to.created_at,
                            "updated_at": message.reply_to.updated_at,
                            "deleted_at": message.reply_to.deleted_at,
                            "reactions": [],
                            "statuses": [],
                            "sender": None,
                            "reply_to": None
                        }
                    except Exception as fallback_error:
                        print(f"[MESSAGE_SERVICE] ❌ Even fallback failed: {fallback_error}")
                        # Last resort: set to None
                        message_dict["reply_to"] = None
            else:
                if message.reply_to_id:
                    print(f"[MESSAGE_SERVICE] ⚠️ Message {message.id} has reply_to_id but reply_to is None! (Lazy load failed)")

            enriched_messages.append(message_dict)

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

        # Invalidate unread count cache (Messenger/Telegram pattern)
        await invalidate_unread_count_cache(str(user_id), str(conversation_id))
        await invalidate_total_unread_count_cache(str(user_id))
        print(f"[MESSAGE_SERVICE] 🗑️ Invalidated unread count cache for user {user_id} in conversation {conversation_id}")

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

    async def mark_messages_delivered(
        self,
        conversation_id: UUID,
        user_id: UUID,
        message_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Mark messages as delivered (Telegram/Messenger pattern).

        Called automatically when user opens a conversation.
        Transitions messages from SENT → DELIVERED.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            message_ids: Optional list of specific message UUIDs (if None, marks all SENT messages)

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

        # Mark messages as delivered
        count = await self.status_repo.mark_messages_as_delivered(
            conversation_id=conversation_id,
            user_id=user_id,
            message_ids=message_ids
        )
        await self.db.commit()

        # Broadcast message status updates via WebSocket
        if message_ids:
            for message_id in message_ids:
                await self.ws_manager.broadcast_message_status(
                    conversation_id,
                    message_id,
                    user_id,
                    MessageStatusType.DELIVERED.value
                )
        else:
            # If no specific messages, we marked all SENT messages
            # Broadcast to conversation room (all members will update their UI)
            await self.ws_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "messages_delivered",
                    "user_id": str(user_id),
                    "conversation_id": str(conversation_id),
                    "count": count
                }
            )

        print(f"[MESSAGE_SERVICE] ✅ Marked {count} messages as DELIVERED for user {user_id} in conversation {conversation_id}")

        return {
            "success": True,
            "updated_count": count,
            "message": f"Marked {count} messages as delivered"
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

    async def clear_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID
    ) -> int:
        """
        Clear all messages in a conversation (soft delete).

        Args:
            conversation_id: Conversation UUID
            user_id: Requesting user UUID

        Returns:
            Number of messages deleted

        Raises:
            HTTPException: If no access to conversation
        """
        # Verify user has access
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this conversation"
            )

        # Soft delete all messages in the conversation
        from sqlalchemy import update
        from app.models.message import Message
        
        # Update all non-deleted messages to set deleted_at
        result = await self.db.execute(
            update(Message)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.deleted_at.is_(None)
                )
            )
            .values(deleted_at=datetime.utcnow())
        )

        await self.db.commit()
        
        return result.rowcount
