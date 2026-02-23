"""
Message service containing business logic for messaging operations.
Handles message CRUD, reactions, status updates, and integrations.
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
# UUID import removed - using str for ID types

logger = logging.getLogger(__name__)

from app.utils.datetime_utils import utc_now, to_iso_utc

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
from sqlalchemy import select, inspect, desc
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
        conversation_id: str,
        user_id: str
    ) -> bool:
        """
        Verify user is a member of the conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

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

    @staticmethod
    def _refresh_metadata_urls(metadata_json: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Refresh expired signed URLs in message metadata using the stored ossKey.

        OSS signed URLs expire after 7 days. Since sign_url() is a local HMAC
        computation (no network call to OSS), this is free and does not add load
        to the OSS bucket. We simply regenerate fresh 7-day URLs on every fetch.

        Only messages with an ossKey in their metadata are affected — text messages
        and E2EE-encrypted messages that store their own keys are left untouched.
        """
        if not metadata_json or "ossKey" not in metadata_json:
            return metadata_json

        try:
            from app.services.oss_service import OSSService
            oss = OSSService()
            oss_key = metadata_json["ossKey"]

            # Determine if file should open inline in browser
            mime_type = metadata_json.get("mimeType", "")
            original_mime = metadata_json.get("encryption", {}).get("originalMimeType", "") if metadata_json.get("encryption") else ""
            effective_mime = original_mime or mime_type
            viewable_types = [
                "application/pdf",
                "image/",   # all image/* types
                "video/",   # all video/* types — browser can stream inline
                "text/plain",
            ]
            is_viewable = any(effective_mime.startswith(t) or effective_mime == t for t in viewable_types)
            file_name = metadata_json.get("fileName")

            refreshed = dict(metadata_json)
            refreshed["fileUrl"] = oss.generate_signed_url(
                oss_key,
                inline=is_viewable,
                filename=file_name if is_viewable else None,
            )

            # Refresh thumbnail URL if present
            thumb_key = metadata_json.get("thumbnailOssKey")
            if thumb_key:
                refreshed["thumbnailUrl"] = oss.generate_signed_url(thumb_key)

            return refreshed
        except Exception as e:
            logger.warning(f"[MessageService] Failed to refresh signed URL for key {metadata_json.get('ossKey')}: {e}")
            return metadata_json

    async def _check_user_blocked(
        self,
        sender_id: str,
        recipient_id: str
    ) -> bool:
        """
        Check if sender is blocked by recipient.

        Args:
            sender_id: Sender user ID
            recipient_id: Recipient user ID

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

    async def _update_conversation_timestamp(self, conversation_id: str) -> None:
        """
        Update conversation's updated_at timestamp.

        Args:
            conversation_id: Conversation ID
        """
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            conversation.updated_at = utc_now()
            await self.db.flush()

    def _compute_message_status(
        self,
        message: Message,
        current_user_id: Optional[str] = None
    ) -> str:
        """
        Compute single aggregated status field for message (Telegram/Messenger pattern).

        Logic:
        - For sent messages (current_user is sender): Aggregate all recipients' statuses
          - If ANY recipient has "sent" → return "sent"
          - If ALL have "delivered" or better → return "delivered"
          - If ALL have "read" → return "read"
        - For received messages: Return "sent" (recipients don't track their own status)
        - Default: "sent"

        Args:
            message: Message instance with loaded statuses
            current_user_id: Optional current user ID (for determining sender)

        Returns:
            Status string: "sent", "delivered", or "read"
        """
        # If no statuses, default to sent
        if not message.statuses:
            return "sent"

        # If current user is the sender, compute aggregated status from recipients
        is_sender = current_user_id and message.sender_id == current_user_id

        if is_sender:
            # Get all recipient statuses (exclude sender's own status)
            recipient_statuses = [
                s.status for s in message.statuses
                if s.user_id != message.sender_id
            ]

            if not recipient_statuses:
                # No recipients yet (shouldn't happen in normal flow)
                return "sent"

            # Aggregate using "least common denominator" approach
            # If ANY recipient is at "sent", show "sent"
            # If ALL are "delivered" or "read", show "delivered"
            # If ALL are "read", show "read"
            has_sent = any(s == MessageStatusType.SENT for s in recipient_statuses)
            all_read = all(s == MessageStatusType.READ for s in recipient_statuses)
            all_delivered_or_read = all(
                s in (MessageStatusType.DELIVERED, MessageStatusType.READ)
                for s in recipient_statuses
            )

            if has_sent:
                return "sent"
            elif all_read:
                return "read"
            elif all_delivered_or_read:
                return "delivered"
            else:
                return "sent"
        else:
            # For received messages, return current user's own status
            # This is needed for frontend to track if they've read the message
            if current_user_id:
                # Find current user's status in the statuses array
                user_status = next(
                    (s.status for s in message.statuses if s.user_id == current_user_id),
                    MessageStatusType.SENT  # Default if not found
                )
                # Return the string value
                return user_status.value if hasattr(user_status, 'value') else str(user_status)
            return "sent"

    async def _enrich_message_with_user_data(
        self,
        message: Message,
        current_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich message with TMS user data and compute aggregated status.

        Args:
            message: Message instance
            current_user_id: Optional current user ID for status computation

        Returns:
            Message dict with enriched user data and computed status field
        """
        message_dict = {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "type": message.type,
            "metadata_json": self._refresh_metadata_urls(message.metadata_json),
            "reply_to_id": message.reply_to_id,
            "is_edited": message.is_edited,
            "sequence_number": message.sequence_number,  # NEW: Include sequence number
            "encrypted": message.encrypted,
            "encryption_version": message.encryption_version,
            "sender_key_id": message.sender_key_id,
            # Convert datetime objects to ISO format strings with 'Z' suffix (UTC indicator)
            "created_at": to_iso_utc(message.created_at),
            "updated_at": to_iso_utc(message.updated_at),
            "deleted_at": to_iso_utc(message.deleted_at),
            "reactions": [
                {
                    "id": r.id,
                    "message_id": r.message_id,
                    "user_id": r.user_id,
                    "emoji": r.emoji,
                    "created_at": to_iso_utc(r.created_at)
                }
                for r in message.reactions
            ],
            "statuses": [
                {
                    "message_id": s.message_id,
                    "user_id": s.user_id,
                    "status": s.status,
                    "timestamp": to_iso_utc(s.timestamp)
                }
                for s in message.statuses
            ],
            # Add computed status field (Telegram/Messenger pattern)
            "status": self._compute_message_status(message, current_user_id),
            # Initialize poll field as None (will be populated below if message is poll type)
            "poll": None
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
            logger.debug("[ENRICH] Message %s has reply_to_id: %s", message.id, message.reply_to_id)

            # Check if reply_to is loaded without triggering lazy load
            reply_to_loaded = False
            try:
                insp = inspect(message)
                if 'reply_to' not in insp.unloaded and message.reply_to is not None:
                    reply_to_loaded = True
                    logger.debug("[ENRICH] reply_to object loaded: True")
            except Exception:
                # If inspection fails, try direct access carefully
                try:
                    if message.reply_to is not None:
                        reply_to_loaded = True
                        logger.debug("[ENRICH] reply_to object loaded via direct access: True")
                except Exception:
                    logger.debug("[ENRICH] reply_to not loaded, cannot access without triggering lazy load")

            if reply_to_loaded:
                try:
                    logger.debug("[ENRICH] Recursively enriching reply_to message: %s", message.reply_to.id)
                    message_dict["reply_to"] = await self._enrich_message_with_user_data(
                        message.reply_to,
                        current_user_id  # Pass through for consistent status computation
                    )
                except Exception as e:
                    logger.debug("[MESSAGE_SERVICE] Failed to enrich reply_to: %s", e)
                    # Fallback: return ALL required fields for MessageResponse schema
                    try:
                        message_dict["reply_to"] = {
                            "id": message.reply_to.id,
                            "conversation_id": message.reply_to.conversation_id,
                            "sender_id": message.reply_to.sender_id,
                            "content": message.reply_to.content,
                            "type": message.reply_to.type,
                            "metadata_json": self._refresh_metadata_urls(message.reply_to.metadata_json or {}),
                            "reply_to_id": message.reply_to.reply_to_id,
                            "is_edited": message.reply_to.is_edited,
                            # Convert datetime objects to ISO format strings with 'Z' suffix
                            "created_at": to_iso_utc(message.reply_to.created_at),
                            "updated_at": to_iso_utc(message.reply_to.updated_at),
                            "deleted_at": to_iso_utc(message.reply_to.deleted_at),
                            "reactions": [],
                            "statuses": [],
                            "sender": None,
                            "reply_to": None
                        }
                    except Exception as fallback_error:
                        logger.debug("[MESSAGE_SERVICE] Even fallback failed: %s", fallback_error)
                        # If even basic access fails, set to None
                        message_dict["reply_to"] = None
            else:
                logger.debug("[ENRICH] reply_to_id exists but reply_to object is not loaded, setting to None")
                message_dict["reply_to"] = None
        else:
            # Explicitly set to None if no reply_to_id
            message_dict["reply_to"] = None

        # Enrich poll data if message type is POLL
        if message.type == MessageType.POLL:
            try:
                # Import poll service to build poll response
                from app.services.poll_service import PollService
                from app.models.poll import Poll

                # Get poll for this message
                result = await self.db.execute(
                    select(Poll).where(Poll.message_id == message.id)
                )
                poll = result.scalar_one_or_none()

                if poll:
                    # Use PollService to build complete poll response with vote counts
                    poll_service = PollService(self.db)
                    poll_data = await poll_service._build_poll_response(poll, current_user_id)
                    message_dict["poll"] = poll_data.model_dump(by_alias=True, mode='json')
                else:
                    logger.warning("[ENRICH] Message %s is type POLL but no poll found", message.id)
                    message_dict["poll"] = None
            except Exception as e:
                logger.error("[MESSAGE_SERVICE] Failed to load poll data: %s", e, exc_info=True)
                message_dict["poll"] = None

        return message_dict

    async def send_message(
        self,
        sender_id: str,
        conversation_id: str,
        content: Optional[str],
        message_type: MessageType = MessageType.TEXT,
        metadata_json: Dict[str, Any] = None,
        reply_to_id: Optional[str] = None,
        encrypted: bool = False,
        encryption_version: Optional[int] = None,
        sender_key_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a new message.

        Args:
            sender_id: Sender user ID
            conversation_id: Conversation ID
            content: Message content
            message_type: Type of message
            metadata_json: Message metadata
            reply_to_id: ID of message being replied to
            encrypted: Whether the message is E2EE encrypted
            encryption_version: Encryption protocol version
            sender_key_id: Sender key ID for group messages

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

        # Get next sequence number (inside transaction, before message creation)
        # This must happen atomically to prevent race conditions
        sequence_number = await self.message_repo.get_next_sequence_number(conversation_id)

        # Create message
        message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            type=message_type,
            metadata_json=metadata_json or {},
            reply_to_id=reply_to_id,
            sequence_number=sequence_number,  # NEW: Include sequence number
            encrypted=encrypted,
            encryption_version=encryption_version,
            sender_key_id=sender_key_id,
        )

        # CRITICAL FIX: Ensure message.id is populated before creating statuses
        # Flush to database and refresh instance to get id
        await self.db.flush()
        await self.db.refresh(message)

        # DEBUG: Verify message.id is not None
        if not message.id:
            raise RuntimeError(f"Message id is None after flush/refresh - cannot create statuses")

        # Get conversation members for status tracking
        result = await self.db.execute(
            select(ConversationMember)
            .where(ConversationMember.conversation_id == conversation_id)
        )
        members = result.scalars().all()

        # DEFENSIVE: Ensure message.id is valid before creating statuses
        if not message.id:
            raise RuntimeError(
                f"Cannot create message statuses: message.id is None "
                f"(conversation_id={conversation_id}, sender_id={sender_id})"
            )

        logger.debug("[MESSAGE_SERVICE] Creating statuses for %d members (message_id=%s)", len(members), message.id)

        # Create message statuses for all members
        # Messenger-style: DELIVERED if recipient is online, SENT if offline
        try:
            # Get globally online users from Redis (accurate across all workers)
            from app.core.cache import get_online_user_ids
            online_user_ids = await get_online_user_ids()

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
                        # Messenger-style: DELIVERED if online, SENT if offline
                        if str(member.user_id) in online_user_ids:
                            await self.status_repo.upsert_status(
                                message.id,
                                member.user_id,
                                MessageStatusType.DELIVERED
                            )
                        else:
                            await self.status_repo.upsert_status(
                                message.id,
                                member.user_id,
                                MessageStatusType.SENT
                            )
        except Exception as status_error:
            logger.error("[MESSAGE_SERVICE] Failed to create message statuses: %s", status_error)
            # Rollback to prevent partial status creation
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create message statuses: {str(status_error)}"
            )

        # Update conversation timestamp
        await self._update_conversation_timestamp(conversation_id)

        # Commit transaction
        await self.db.commit()

        # Invalidate unread count cache for all conversation members (except sender)
        # Following Messenger/Telegram pattern: new message = increment unread for recipients
        for member in members:
            if member.user_id != sender_id:
                await invalidate_unread_count_cache(str(member.user_id), str(conversation_id))
                await invalidate_total_unread_count_cache(str(member.user_id))

        # Reload message with relations
        message = await self.message_repo.get_with_relations(message.id)

        # Enrich with TMS user data (pass sender_id as user_id for status computation)
        enriched_message = await self._enrich_message_with_user_data(message, sender_id)

        # Convert datetimes to strings for JSON serialization with 'Z' suffix
        def convert_to_json_serializable(obj):
            """Recursively convert datetime objects to UTC ISO strings with 'Z' suffix."""
            from datetime import datetime
            if isinstance(obj, dict):
                return {k: convert_to_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            elif isinstance(obj, datetime):
                return to_iso_utc(obj)
            else:
                return obj
        
        # Prepare message for WebSocket broadcast (all datetimes as strings)
        broadcast_message = convert_to_json_serializable(enriched_message)

        # Broadcast new message via WebSocket
        try:
            await self.ws_manager.broadcast_new_message(
                conversation_id,
                broadcast_message
            )
        except Exception as broadcast_error:
            logger.error(f"[send_message] Broadcast failed: {broadcast_error}", exc_info=True)

        return enriched_message

    async def get_message(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a single message by ID.

        Args:
            message_id: Message ID
            user_id: Requesting user ID

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

        return await self._enrich_message_with_user_data(message, user_id)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 10,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """
        Get messages for a conversation with pagination.
        OPTIMIZED: Uses batch fetching to avoid N+1 problem.

        Implements Messenger-style message visibility:
        - Messages deleted for everyone (deleted_at set) are shown as "User removed a message"
        - Messages deleted for me (in user_deleted_messages) are completely hidden

        Args:
            conversation_id: Conversation ID
            user_id: Requesting user ID
            limit: Number of messages
            cursor: Cursor for pagination

        Returns:
            Tuple of (enriched messages, next_cursor, has_more)

        Raises:
            HTTPException: If no access
        """
        logger.debug("[MESSAGE_SERVICE] get_conversation_messages: conversation=%s limit=%d", conversation_id, limit)

        # Verify user is conversation member
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Get messages (include deleted messages to show "User removed a message" placeholder)
        messages, next_cursor, has_more = await self.message_repo.get_conversation_messages(
            conversation_id,
            limit,
            cursor,
            include_deleted=True  # FIX: Include soft-deleted messages (Messenger/Telegram pattern)
        )

        # Filter out messages that are deleted "for me" (per-user deletion)
        if messages:
            from app.models.user_deleted_message import UserDeletedMessage

            # Get message IDs that this user has deleted "for me"
            message_ids = [msg.id for msg in messages]
            result = await self.db.execute(
                select(UserDeletedMessage.message_id).where(
                    UserDeletedMessage.user_id == user_id,
                    UserDeletedMessage.message_id.in_(message_ids)
                )
            )
            user_deleted_ids = set(row[0] for row in result.all())

            # Filter out per-user deleted messages
            if user_deleted_ids:
                messages = [msg for msg in messages if msg.id not in user_deleted_ids]
        
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
                logger.warning("[MESSAGE_SERVICE] Batch user fetch failed: %s", e)

        enriched_messages = []
        for message in messages:
            message_dict = {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "type": message.type,
                "metadata_json": self._refresh_metadata_urls(message.metadata_json),
                "reply_to_id": message.reply_to_id,
                "is_edited": message.is_edited,
                "sequence_number": message.sequence_number,  # NEW: Include sequence number
                "encrypted": message.encrypted,
                "encryption_version": message.encryption_version,
                "sender_key_id": message.sender_key_id,
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
                ],
                # Add computed status field (Telegram/Messenger pattern)
                "status": self._compute_message_status(message, user_id)
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

            # Enrich poll data if message type is POLL
            if message.type == MessageType.POLL:
                try:
                    from app.services.poll_service import PollService
                    from app.models.poll import Poll

                    result = await self.db.execute(
                        select(Poll).where(Poll.message_id == message.id)
                    )
                    poll = result.scalar_one_or_none()

                    if poll:
                        poll_service = PollService(self.db)
                        poll_data = await poll_service._build_poll_response(poll, user_id)
                        message_dict["poll"] = poll_data.model_dump(by_alias=True, mode='json')
                    else:
                        logger.warning("[MESSAGE_SERVICE] Message %s is type POLL but no poll found", message.id)
                        message_dict["poll"] = None
                except Exception as e:
                    logger.error("[MESSAGE_SERVICE] Failed to load poll data: %s", e, exc_info=True)
                    message_dict["poll"] = None
            else:
                message_dict["poll"] = None

            # Handle reply_to enrichment (recursive)
            if message.reply_to:
                # For replied messages, use individual enrichment
                # (these are typically 1-2 messages, not worth batch optimization)
                try:
                    message_dict["reply_to"] = await self._enrich_message_with_user_data(
                        message.reply_to,
                        user_id  # Pass through for consistent status computation
                    )
                except Exception as e:
                    logger.debug("[MESSAGE_SERVICE] Failed to enrich reply_to: %s", e)
                    # Fallback: Include ALL required fields for MessageResponse schema
                    try:
                        message_dict["reply_to"] = {
                            "id": message.reply_to.id,
                            "conversation_id": message.reply_to.conversation_id,
                            "sender_id": message.reply_to.sender_id,
                            "content": message.reply_to.content,
                            "type": message.reply_to.type,
                            "metadata_json": self._refresh_metadata_urls(message.reply_to.metadata_json or {}),
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
                        logger.debug("[MESSAGE_SERVICE] Even fallback failed: %s", fallback_error)
                        message_dict["reply_to"] = None
            else:
                if message.reply_to_id:
                    logger.debug("[MESSAGE_SERVICE] Message %s has reply_to_id but reply_to is None (lazy load failed)", message.id)

            enriched_messages.append(message_dict)

        return enriched_messages, next_cursor, has_more

    async def edit_message(
        self,
        message_id: str,
        user_id: str,
        new_content: str
    ) -> Dict[str, Any]:
        """
        Edit a message.

        Args:
            message_id: Message ID
            user_id: User ID (must be sender)
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
            updated_at=utc_now()
        )

        await self.db.commit()

        # Reload with relations and enrich
        updated_message = await self.message_repo.get_with_relations(message_id)
        enriched_message = await self._enrich_message_with_user_data(updated_message, user_id)

        # Broadcast message edit via WebSocket
        await self.ws_manager.broadcast_message_edited(
            message.conversation_id,
            enriched_message
        )

        return enriched_message

    async def delete_message(
        self,
        message_id: str,
        user_id: str,
        delete_for_everyone: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a message (Messenger-style deletion).

        Supports two modes:
        - Delete for Me: Only hides the message for the requesting user
        - Delete for Everyone: Soft deletes the message for all users (sender only)

        Args:
            message_id: Message ID
            user_id: User ID
            delete_for_everyone: If True, delete for all users (sender only can do this)

        Returns:
            Success response with deleted_at timestamp

        Raises:
            HTTPException: If not found or no permission
        """
        import logging
        logger = logging.getLogger(__name__)

        message = await self.message_repo.get(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        # Check if message is already deleted for everyone
        if message.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message already deleted for everyone"
            )

        # Verify user has access to the conversation
        if not await self._verify_conversation_membership(message.conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this conversation"
            )

        deleted_at = utc_now()

        if delete_for_everyone:
            # Delete for Everyone: Only sender can do this
            if message.sender_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the sender can delete a message for everyone"
                )

            # Soft delete (marks deleted_at timestamp) - affects all users
            deleted_message = await self.message_repo.soft_delete(message_id)
            await self.db.commit()

            # Broadcast message:edit event so all clients update
            try:
                deleted_message_with_relations = await self.message_repo.get_with_relations(message_id)
                enriched_message = await self._enrich_message_with_user_data(deleted_message_with_relations, user_id)

                await self.ws_manager.broadcast_message_edited(
                    conversation_id=message.conversation_id,
                    message_data=enriched_message
                )
                logger.info(f"[DELETE_MESSAGE] Broadcasted delete_for_everyone for message {message_id}")
            except Exception as e:
                logger.error(f"[DELETE_MESSAGE] Failed to broadcast: {e}", exc_info=True)

            return {
                "success": True,
                "message": "Message deleted for everyone",
                "deleted_at": deleted_message.deleted_at,
                "deleted_for_everyone": True
            }
        else:
            # Delete for Me: Add entry to user_deleted_messages table
            from app.models.user_deleted_message import UserDeletedMessage
            from sqlalchemy import select

            # Check if already deleted for this user
            result = await self.db.execute(
                select(UserDeletedMessage).where(
                    UserDeletedMessage.user_id == user_id,
                    UserDeletedMessage.message_id == message_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message already deleted for you"
                )

            # Create per-user deletion record
            user_deletion = UserDeletedMessage(
                user_id=user_id,
                message_id=message_id,
                deleted_at=deleted_at
            )
            self.db.add(user_deletion)
            await self.db.commit()

            logger.info(f"[DELETE_MESSAGE] Deleted message {message_id} for user {user_id} only")

            return {
                "success": True,
                "message": "Message deleted for you",
                "deleted_at": deleted_at,
                "deleted_for_everyone": False
            }

    async def add_reaction(
        self,
        message_id: str,
        user_id: str,
        emoji: str
    ) -> Dict[str, Any]:
        """
        Add a reaction to a message.

        Implements Telegram/Messenger pattern: If user already has a different reaction,
        automatically switch to the new emoji (remove old, add new).

        Args:
            message_id: Message ID
            user_id: User ID
            emoji: Emoji string

        Returns:
            Created reaction

        Raises:
            HTTPException: If message not found or already reacted with same emoji
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

        # Check if user already has ANY reaction on this message
        from app.models.message import MessageReaction
        from sqlalchemy import select, and_

        result = await self.db.execute(
            select(MessageReaction).where(
                and_(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id
                )
            )
        )
        existing_reaction = result.scalar_one_or_none()

        # If user already reacted with a DIFFERENT emoji, remove it first (switch behavior)
        old_emoji = None
        if existing_reaction and existing_reaction.emoji != emoji:
            old_emoji = existing_reaction.emoji
            # Remove the old reaction
            await self.reaction_repo.remove_reaction(message_id, user_id, old_emoji)
            # Broadcast removal via WebSocket
            await self.ws_manager.broadcast_reaction_removed(
                message.conversation_id,
                message_id,
                user_id,
                old_emoji
            )

        # Add the new reaction
        reaction = await self.reaction_repo.add_reaction(message_id, user_id, emoji)

        if not reaction:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already reacted with this emoji"
            )

        await self.db.commit()

        reaction_data = {
            # Convert objects to strings for JSON serialization
            "id": str(reaction.id),
            "message_id": str(reaction.message_id),
            "user_id": str(reaction.user_id),
            "emoji": reaction.emoji,
            # Convert datetime to UTC ISO format string with 'Z' suffix
            "created_at": to_iso_utc(reaction.created_at)
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
        message_id: str,
        user_id: str,
        emoji: str
    ) -> Dict[str, Any]:
        """
        Remove a reaction from a message.

        Args:
            message_id: Message ID
            user_id: User ID
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
        message_ids: List[str],
        user_id: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Mark multiple messages as read and update last_read_at timestamp.

        Args:
            message_ids: List of message IDs
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            Success response with count

        Raises:
            HTTPException: If no access
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(
            f"[MESSAGE_SERVICE] 📝 mark_messages_read called: "
            f"user_id={user_id}, conversation_id={conversation_id}, "
            f"message_count={len(message_ids)}"
        )

        # LOG: Membership verification
        logger.info(f"[MESSAGE_SERVICE] 🔐 Verifying conversation membership...")
        if not await self._verify_conversation_membership(conversation_id, user_id):
            logger.warning(
                f"[MESSAGE_SERVICE] ⛔ Membership verification failed: "
                f"user_id={user_id}, conversation_id={conversation_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )
        logger.info(f"[MESSAGE_SERVICE] ✅ Membership verified")

        # LOG: Database update
        logger.info(f"[MESSAGE_SERVICE] 💾 Updating message statuses to READ...")
        try:
            count = await self.status_repo.mark_messages_as_read(message_ids, user_id)
            logger.info(f"[MESSAGE_SERVICE] ✅ Updated {count} message statuses")
        except Exception as e:
            logger.error(
                f"[MESSAGE_SERVICE] ❌ Failed to update message statuses: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise

        # LOG: last_read_at update
        if message_ids:
            logger.info(f"[MESSAGE_SERVICE] 📅 Updating last_read_at timestamp...")
            try:
                # Get the latest message timestamp from the batch
                latest_message_query = (
                    select(Message.created_at)
                    .where(Message.id.in_(message_ids))
                    .order_by(desc(Message.created_at))
                    .limit(1)
                )
                result = await self.db.execute(latest_message_query)
                latest_timestamp = result.scalar_one_or_none()

                if latest_timestamp:
                    logger.info(f"[MESSAGE_SERVICE] ⏰ Latest message timestamp: {latest_timestamp}")

                    # Update last_read_at for this conversation member
                    from app.repositories.conversation_repo import ConversationMemberRepository
                    member_repo = ConversationMemberRepository(self.db)
                    member = await member_repo.get_member(conversation_id, user_id)

                    if member:
                        # Only update if new timestamp is later than current last_read_at
                        if member.last_read_at is None or latest_timestamp > member.last_read_at:
                            member.last_read_at = latest_timestamp
                            logger.info(
                                f"[MESSAGE_SERVICE] 📅 Updated last_read_at: "
                                f"{member.last_read_at} → {latest_timestamp}"
                            )
                        else:
                            logger.info(
                                f"[MESSAGE_SERVICE] ⏭️ Skipping last_read_at update "
                                f"(current={member.last_read_at}, new={latest_timestamp})"
                            )
                    else:
                        logger.warning(
                            f"[MESSAGE_SERVICE] ⚠️ ConversationMember not found: "
                            f"conversation_id={conversation_id}, user_id={user_id}"
                        )
                else:
                    logger.warning(f"[MESSAGE_SERVICE] ⚠️ No latest timestamp found for messages")
            except Exception as e:
                logger.error(
                    f"[MESSAGE_SERVICE] ❌ Failed to update last_read_at: "
                    f"{type(e).__name__}: {str(e)}"
                )
                # Don't raise - this is not critical, continue with commit

        # LOG: Database commit
        logger.info(f"[MESSAGE_SERVICE] 💾 Committing transaction...")
        try:
            await self.db.commit()
            logger.info(f"[MESSAGE_SERVICE] ✅ Transaction committed")
        except Exception as e:
            logger.error(
                f"[MESSAGE_SERVICE] ❌ Database commit failed: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise

        # LOG: Cache invalidation
        logger.info(f"[MESSAGE_SERVICE] 🗑️ Invalidating cache...")
        try:
            await invalidate_unread_count_cache(str(user_id), str(conversation_id))
            await invalidate_total_unread_count_cache(str(user_id))
            logger.info(f"[MESSAGE_SERVICE] ✅ Cache invalidated")
        except Exception as e:
            logger.error(
                f"[MESSAGE_SERVICE] ⚠️ Cache invalidation failed (non-critical): "
                f"{type(e).__name__}: {str(e)}"
            )
            # Don't raise - cache invalidation failure is not critical

        # LOG: WebSocket broadcast
        logger.info(f"[MESSAGE_SERVICE] 📡 Broadcasting status updates via WebSocket...")
        try:
            for message_id in message_ids:
                await self.ws_manager.broadcast_message_status(
                    conversation_id,
                    message_id,
                    user_id,
                    MessageStatusType.READ.value
                )
            logger.info(f"[MESSAGE_SERVICE] ✅ Broadcasted {len(message_ids)} status updates")
        except Exception as e:
            logger.error(
                f"[MESSAGE_SERVICE] ⚠️ WebSocket broadcast failed (non-critical): "
                f"{type(e).__name__}: {str(e)}"
            )
            # Don't raise - broadcast failure is not critical

        logger.info(
            f"[MESSAGE_SERVICE] ✅ mark_messages_read completed successfully: "
            f"updated_count={count}"
        )

        return {
            "success": True,
            "updated_count": count,
            "message": f"Marked {count} messages as read"
        }

    async def mark_conversation_messages_read(
        self,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Mark all unread messages in a conversation as READ (Messenger-style).

        Called automatically when user opens/joins a conversation.
        Transitions messages from SENT/DELIVERED → READ for all messages
        from other users in the conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID (the reader)

        Returns:
            Success response with updated count

        Raises:
            HTTPException: If user is not a member of the conversation
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(
            f"[MESSAGE_SERVICE] 📖 mark_conversation_messages_read: "
            f"conversation_id={conversation_id}, user_id={user_id}"
        )

        # Verify user is conversation member
        if not await self._verify_conversation_membership(conversation_id, user_id):
            logger.warning(
                f"[MESSAGE_SERVICE] ⛔ Membership verification failed: "
                f"user_id={user_id}, conversation_id={conversation_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Mark all unread messages as READ
        count, message_ids = await self.status_repo.mark_all_as_read_in_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )

        if count > 0:
            await self.db.commit()

            # Invalidate cache
            try:
                await invalidate_unread_count_cache(str(user_id), str(conversation_id))
                await invalidate_total_unread_count_cache(str(user_id))
            except Exception as e:
                logger.warning(f"[MESSAGE_SERVICE] Cache invalidation failed (non-critical): {e}")

            # Broadcast status updates via WebSocket
            try:
                for message_id in message_ids:
                    await self.ws_manager.broadcast_message_status(
                        conversation_id,
                        message_id,
                        user_id,
                        MessageStatusType.READ.value
                    )
                logger.info(f"[MESSAGE_SERVICE] ✅ Broadcasted {len(message_ids)} READ status updates")
            except Exception as e:
                logger.warning(f"[MESSAGE_SERVICE] WebSocket broadcast failed (non-critical): {e}")

        logger.info(
            f"[MESSAGE_SERVICE] ✅ mark_conversation_messages_read completed: "
            f"updated_count={count}"
        )

        return {
            "success": True,
            "updated_count": count,
            "message": f"Marked {count} messages as read"
        }

    async def mark_messages_delivered(
        self,
        conversation_id: str,
        user_id: str,
        message_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Mark messages as delivered (Telegram/Messenger pattern).

        Called automatically when user opens a conversation.
        Transitions messages from SENT → DELIVERED.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            message_ids: Optional list of specific message IDs (if None, marks all SENT messages)

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

        logger.debug("[MESSAGE_SERVICE] Marked %d messages as DELIVERED for user %s in conversation %s", count, user_id, conversation_id)

        return {
            "success": True,
            "updated_count": count,
            "message": f"Marked {count} messages as delivered"
        }

    async def mark_all_messages_delivered_for_user(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Mark all pending SENT messages as DELIVERED for a user across all conversations.

        Messenger-style pattern: Called when user comes online (connects to WebSocket).
        This ensures all messages sent while user was offline transition to DELIVERED
        as soon as they're online.

        Args:
            user_id: User ID who just came online

        Returns:
            Success response with count and list of affected conversation IDs
        """
        # Get all conversations where user is a member
        from app.models.conversation import ConversationMember
        result = await self.db.execute(
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
        )
        conversation_ids = [row[0] for row in result.fetchall()]

        if not conversation_ids:
            return {
                "success": True,
                "updated_count": 0,
                "conversation_ids": [],
                "message": "No conversations found"
            }

        total_count = 0
        affected_conversations = []

        # Mark messages as delivered in each conversation
        for conv_id in conversation_ids:
            count = await self.status_repo.mark_messages_as_delivered(
                conversation_id=conv_id,
                user_id=user_id
            )
            if count > 0:
                total_count += count
                affected_conversations.append(conv_id)

        await self.db.commit()

        logger.debug("[MESSAGE_SERVICE] Marked %d messages as DELIVERED for user %s across %d conversations", total_count, user_id, len(affected_conversations))

        return {
            "success": True,
            "updated_count": total_count,
            "conversation_ids": affected_conversations,
            "message": f"Marked {total_count} messages as delivered"
        }

    async def search_messages(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search messages with filters.

        Args:
            query: Search query
            user_id: Requesting user ID
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

        # Search messages (now filtered by user's conversations at database level)
        messages = await self.message_repo.search_messages(
            query,
            user_id,  # Pass user_id to filter at database level
            conversation_id,
            sender_id,
            start_date,
            end_date,
            limit
        )

        # Enrich messages (no filtering needed - already filtered by database)
        enriched_messages = []
        for message in messages:
            enriched_messages.append(
                await self._enrich_message_with_user_data(message, user_id)
            )

        return enriched_messages

    async def clear_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> int:
        """
        Clear all messages in a conversation for the current user only (Messenger-style).

        This creates per-user deletion records for all messages in the conversation,
        allowing each user to clear their own chat history without affecting others.

        Args:
            conversation_id: Conversation ID
            user_id: Requesting user ID

        Returns:
            Number of messages cleared for this user

        Raises:
            HTTPException: If no access to conversation
        """
        import logging
        logger = logging.getLogger(__name__)

        # Verify user has access
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this conversation"
            )

        from sqlalchemy import select, and_
        from app.models.message import Message
        from app.models.user_deleted_message import UserDeletedMessage

        # Get all message IDs in this conversation that aren't already deleted for everyone
        # and aren't already deleted for this user
        subquery = select(UserDeletedMessage.message_id).where(
            UserDeletedMessage.user_id == user_id
        ).scalar_subquery()

        result = await self.db.execute(
            select(Message.id).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.deleted_at.is_(None),  # Not deleted for everyone
                    Message.id.not_in(subquery)     # Not already deleted for this user
                )
            )
        )
        message_ids = [row[0] for row in result.all()]

        if not message_ids:
            logger.info(f"[CLEAR_CONVERSATION] No messages to clear for user {user_id}")
            return 0

        # Batch insert per-user deletion records
        deleted_at = utc_now()
        user_deletions = [
            UserDeletedMessage(
                user_id=user_id,
                message_id=msg_id,
                deleted_at=deleted_at
            )
            for msg_id in message_ids
        ]

        self.db.add_all(user_deletions)
        await self.db.commit()

        logger.info(
            f"[CLEAR_CONVERSATION] Cleared {len(message_ids)} messages "
            f"for user {user_id} in conversation {conversation_id}"
        )

        return len(message_ids)

    async def handle_file_upload(
        self,
        sender_id: str,
        conversation_id: str,
        file: "UploadFile",
        reply_to_id: Optional[str] = None,
        duration: Optional[int] = None,
        encrypted: bool = False,
        encryption_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle file upload and create message.

        Uploads file to OSS, generates thumbnail if applicable, and creates
        a message with the appropriate type (IMAGE, FILE, or VOICE).

        For E2EE encrypted files: skips MIME validation (ciphertext is always
        application/octet-stream) and uses originalMimeType from encryption
        metadata to determine message type (Messenger/WhatsApp pattern).

        Args:
            sender_id: Sender user ID
            conversation_id: Conversation ID
            file: Uploaded file (FastAPI UploadFile)
            reply_to_id: Optional message ID to reply to
            duration: Optional duration for voice messages (seconds)
            encrypted: Whether the file is E2EE encrypted
            encryption_metadata: Encryption metadata with originalMimeType, etc.

        Returns:
            Created message with enriched data

        Raises:
            HTTPException: If validation fails or upload fails
        """
        from fastapi import UploadFile
        from app.services.oss_service import OSSService
        from app.config import settings

        logger.debug("[MESSAGE_SERVICE] Starting file upload: %s (conversation=%s, encrypted=%s)", file.filename, conversation_id, encrypted)

        # Initialize OSS service
        oss_service = OSSService()

        allowed_types = settings.get_allowed_file_types_list()
        max_size = settings.max_upload_size

        if encrypted and encryption_metadata:
            # Encrypted files: skip MIME validation (ciphertext is always application/octet-stream)
            # Only validate file size (security boundary)
            logger.debug("[MESSAGE_SERVICE] Encrypted upload — skipping MIME validation")
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            if file_size == 0:
                raise HTTPException(status_code=400, detail="File is empty")
            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large ({file_size} bytes, max {max_size})"
                )
            # Use original MIME type from encryption metadata for message type detection
            content_type = encryption_metadata.get("originalMimeType", "application/octet-stream")
        else:
            oss_service.validate_file(file, allowed_types, max_size)
            content_type = file.content_type or "application/octet-stream"

        if content_type.startswith('image/'):
            message_type = MessageType.IMAGE
        elif content_type.startswith('audio/'):
            message_type = MessageType.VOICE
        elif content_type.startswith('video/'):
            message_type = MessageType.FILE  # Videos are treated as files for now
        else:
            message_type = MessageType.FILE

        # Upload file to OSS
        folder = f"messages/{conversation_id}"
        upload_result = await oss_service.upload_file(file, folder=folder)

        # Generate thumbnail for images (skip for encrypted files — server can't read ciphertext)
        thumbnail_url = None
        thumbnail_oss_key = None
        if message_type == MessageType.IMAGE and not encrypted:
            try:
                # Reset file pointer and read content for thumbnail
                file.file.seek(0)
                image_bytes = await file.read()

                thumbnail_result = await oss_service.generate_image_thumbnail(
                    image_bytes,
                    folder=f"thumbnails/{conversation_id}"
                )

                if thumbnail_result:
                    thumbnail_url = thumbnail_result[1]
                    thumbnail_oss_key = thumbnail_result[2]
            except Exception as e:
                logger.warning("[MESSAGE_SERVICE] Thumbnail generation failed: %s", e)
                # Non-critical - continue without thumbnail

        # Build metadata
        metadata_json = {
            "fileName": file.filename,
            "fileSize": upload_result["file_size"],
            "fileUrl": upload_result["url"],
            "mimeType": content_type,
            "ossKey": upload_result["oss_key"]
        }

        # Note: OSS bucket doesn't support response-content-disposition override
        # Browser handles file viewing natively (PDFs show inline, others download)

        # Add thumbnail URL and key if available (key enables URL refresh on fetch)
        if thumbnail_url:
            metadata_json["thumbnailUrl"] = thumbnail_url
        if thumbnail_oss_key:
            metadata_json["thumbnailOssKey"] = thumbnail_oss_key

        # Add duration for voice messages
        if message_type == MessageType.VOICE and duration:
            metadata_json["duration"] = duration

        # Add encryption metadata if present (E2EE file uploads)
        if encrypted and encryption_metadata:
            metadata_json["encryption"] = encryption_metadata

        # Create message using existing send_message method
        # Use filename as content for file messages
        content = file.filename

        message = await self.send_message(
            sender_id=sender_id,
            conversation_id=conversation_id,
            content=content,
            message_type=message_type,
            metadata_json=metadata_json,
            reply_to_id=reply_to_id,
            encrypted=encrypted,
            encryption_version=1 if encrypted else None,
        )

        return message
