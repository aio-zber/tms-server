"""
Conversation service containing business logic for conversation operations.
Handles conversation CRUD, member management, and integrations.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
# UUID import removed - using str for ID types

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationType, ConversationRole
from app.repositories.conversation_repo import (
    ConversationRepository,
    ConversationMemberRepository
)
from app.core.tms_client import tms_client, TMSAPIException


class ConversationService:
    """Service for conversation operations with business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize conversation service.

        Args:
            db: Database session
        """
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.member_repo = ConversationMemberRepository(db)

    async def _enrich_conversation_with_user_data(
        self,
        conversation: Conversation,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Enrich conversation with TMS user data and member info.

        Args:
            conversation: Conversation instance
            user_id: Current user UUID

        Returns:
            Conversation dict with enriched user data
        """
        conversation_dict = {
            "id": conversation.id,
            "type": conversation.type,
            "name": conversation.name,
            "avatar_url": conversation.avatar_url,
            "created_by": conversation.created_by,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "members": [],
            "member_count": 0,
            "unread_count": 0
        }

        # Fetch creator data from TMS
        if conversation.created_by:
            try:
                # Get local user first
                from app.models.user import User
                from sqlalchemy import select

                result = await self.db.execute(
                    select(User).where(User.id == conversation.created_by)
                )
                creator = result.scalar_one_or_none()

                if creator:
                    try:
                        creator_data = await tms_client.get_user(
                            creator.tms_user_id,
                            use_cache=True
                        )
                        conversation_dict["creator"] = creator_data
                    except (TMSAPIException, Exception):
                        # Fallback to local DB data
                        conversation_dict["creator"] = {
                            "id": str(creator.id),
                            "tms_user_id": creator.tms_user_id,
                            "email": creator.email or "",
                            "first_name": creator.first_name or "",
                            "last_name": creator.last_name or "",
                            "image": creator.image or "",
                        }
            except Exception:
                conversation_dict["creator"] = {
                    "id": str(conversation.created_by)
                }

        # Enrich members
        enriched_members = []
        for member in conversation.members:
            member_dict = {
                "user_id": member.user_id,
                "role": member.role,
                "joined_at": member.joined_at,
                "last_read_at": member.last_read_at,
                "is_muted": member.is_muted,
                "mute_until": member.mute_until
            }

            # Fetch user data from TMS, with local DB fallback
            if member.user:
                # Build local DB fallback data (always available, no API call needed)
                local_user_data = {
                    "id": str(member.user_id),
                    "tms_user_id": member.user.tms_user_id,
                    "email": member.user.email or "",
                    "first_name": member.user.first_name or "",
                    "last_name": member.user.last_name or "",
                    "middle_name": member.user.middle_name or "",
                    "username": member.user.username or "",
                    "image": member.user.image or "",
                    "role": member.user.role or "",
                    "position_title": member.user.position_title or "",
                    "division": member.user.division or "",
                    "department": member.user.department or "",
                }

                try:
                    # Use API Key authentication for server-to-server calls (PREFERRED METHOD)
                    user_data = await tms_client.get_user_by_id_with_api_key(
                        member.user.tms_user_id,
                        use_cache=True
                    )
                    member_dict["user"] = user_data
                except (TMSAPIException, Exception):
                    # Fallback to local DB data (has name, email, image from last sync)
                    member_dict["user"] = local_user_data

            enriched_members.append(member_dict)

        conversation_dict["members"] = enriched_members
        conversation_dict["member_count"] = len(enriched_members)

        # Compute display_name and avatar_url for DMs (Telegram/Messenger pattern)
        # For DMs: display the OTHER user's name and profile image
        # For groups: use the group name and group avatar
        if conversation.type == ConversationType.DM:
            # Find the other user (not current user)
            other_members = [m for m in enriched_members if m["user_id"] != user_id]

            if other_members and "user" in other_members[0]:
                other_user_data = other_members[0]["user"]
                # Use first_name + last_name as display name
                first_name = other_user_data.get("first_name", "")
                last_name = other_user_data.get("last_name", "")
                display_name = f"{first_name} {last_name}".strip()

                # Fallback to email if no name available
                if not display_name:
                    display_name = other_user_data.get("email", "Direct Message")

                conversation_dict["display_name"] = display_name

                # For DMs, use the other user's profile image as avatar (Messenger/Telegram pattern)
                other_user_image = other_user_data.get("image")
                if other_user_image:
                    conversation_dict["avatar_url"] = other_user_image
                    print(f"[CONVERSATION_SERVICE] 💬 DM avatar_url set to other user's image")

                print(f"[CONVERSATION_SERVICE] 💬 DM display_name: '{display_name}'")
            else:
                conversation_dict["display_name"] = "Direct Message"
                print(f"[CONVERSATION_SERVICE] ⚠️ DM has no other user, using fallback")
        else:
            # For groups, use the group name
            conversation_dict["display_name"] = conversation.name or "Group Chat"

        # Get unread count for current user
        unread_count = await self.member_repo.get_unread_count(
            conversation.id,
            user_id
        )
        conversation_dict["unread_count"] = unread_count

        # Get last message
        last_message = await self.conversation_repo.get_last_message(conversation.id)
        if last_message:
            conversation_dict["last_message"] = {
                "id": last_message.id,
                "content": last_message.content,
                "type": last_message.type,
                "sender_id": last_message.sender_id,
                "timestamp": last_message.created_at,  # Frontend expects "timestamp"
                "encrypted": getattr(last_message, 'encrypted', False) or False,
            }

        return conversation_dict

    async def create_conversation(
        self,
        creator_id: str,
        type: ConversationType,
        member_ids: List[str],
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            creator_id: Creator user UUID (automatically added as admin)
            type: Conversation type (dm/group)
            member_ids: List of OTHER member user IDs (excludes creator - creator is added automatically)
            name: Optional conversation name (required for groups)
            avatar_url: Optional avatar URL

        Returns:
            Created conversation with enriched data

        Raises:
            HTTPException: If validation fails
        """
        # Validate group name
        if type == ConversationType.GROUP and not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group conversations must have a name"
            )

        # For DMs, check if conversation already exists
        if type == ConversationType.DM:
            if len(member_ids) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DM conversations must have exactly 1 other member"
                )

            other_user_id = member_ids[0]
            existing_dm = await self.conversation_repo.find_dm_conversation(
                creator_id,
                other_user_id
            )

            if existing_dm:
                # Return existing DM
                return await self._enrich_conversation_with_user_data(
                    existing_dm,
                    creator_id
                )

        # Validate creator is NOT in member_ids (they'll be added automatically as admin)
        if creator_id in member_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Creator is automatically added as admin. Do not include yourself in member_ids."
            )

        # Validate all member IDs exist in local database
        from app.models.user import User
        from sqlalchemy import select

        # Check creator exists
        result = await self.db.execute(select(User).where(User.id == creator_id))
        creator = result.scalar_one_or_none()
        if not creator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Creator user {creator_id} not found"
            )

        # Check all members exist
        for uid in member_ids:
            result = await self.db.execute(select(User).where(User.id == uid))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {uid} not found"
                )

        # Create conversation with members
        conversation = await self.conversation_repo.create_with_members(
            type=type,
            creator_id=creator_id,
            member_ids=member_ids,
            name=name,
            avatar_url=avatar_url
        )

        await self.db.commit()

        # Reload with relations and enrich
        conversation = await self.conversation_repo.get_with_relations(conversation.id)
        return await self._enrich_conversation_with_user_data(conversation, creator_id)

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get a single conversation by ID.

        Args:
            conversation_id: Conversation UUID
            user_id: Requesting user UUID

        Returns:
            Conversation with enriched data

        Raises:
            HTTPException: If not found or no access
        """
        # Verify user is member
        if not await self.member_repo.is_member(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        conversation = await self.conversation_repo.get_with_relations(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        return await self._enrich_conversation_with_user_data(conversation, user_id)

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """
        Get all conversations for a user with pagination.

        Args:
            user_id: User UUID
            limit: Number of conversations
            cursor: Cursor for pagination

        Returns:
            Tuple of (enriched conversations, next_cursor, has_more)
        """
        conversations, next_cursor, has_more = await self.conversation_repo.get_user_conversations(
            user_id,
            limit,
            cursor
        )

        # Enrich conversations
        enriched_conversations = []
        for conversation in conversations:
            enriched_conversations.append(
                await self._enrich_conversation_with_user_data(conversation, user_id)
            )

        return enriched_conversations, next_cursor, has_more

    async def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update conversation details.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID (must be admin)
            name: Updated name
            avatar_url: Updated avatar URL

        Returns:
            Updated conversation

        Raises:
            HTTPException: If not found or no permission
        """
        # Verify user is admin
        if not await self.member_repo.is_admin(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can update conversation details"
            )

        # Verify conversation exists
        conversation = await self.conversation_repo.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # DM conversations cannot be renamed
        if conversation.type == ConversationType.DM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update DM conversation details"
            )

        # Update conversation
        updated_conversation = await self.conversation_repo.update_conversation(
            conversation_id,
            name=name,
            avatar_url=avatar_url
        )

        # Flush but don't commit yet
        await self.db.flush()

        # Create system message
        from app.core.websocket import connection_manager
        from app.models.user import User
        from app.services.system_message_service import SystemMessageService
        from sqlalchemy import select
        import logging
        logger = logging.getLogger(__name__)

        # Get actor
        result = await self.db.execute(select(User).where(User.id == user_id))
        actor = result.scalar_one_or_none()

        system_msg = None
        if actor:
            updates_dict = {}
            if name is not None:
                updates_dict['name'] = name
            if avatar_url is not None:
                updates_dict['avatar_url'] = avatar_url

            try:
                system_msg = await SystemMessageService.create_conversation_updated_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    actor=actor,
                    updates=updates_dict
                )
                # Flush system message
                await self.db.flush()
                logger.info(f"✅ Created system message for conversation_updated event")
            except Exception as msg_error:
                logger.error(f"Failed to create system message: {msg_error}", exc_info=True)
                # Rollback on system message failure
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create system message"
                )

        # Commit all database changes atomically
        await self.db.commit()

        # Broadcast via WebSocket (failures won't affect DB since already committed)
        try:
            if system_msg:
                # Broadcast as regular message
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'sequenceNumber': system_msg.sequence_number,
                    'createdAt': system_msg.created_at.isoformat()
                }

                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )

                logger.info(f"✅ Broadcasted system message for conversation_updated event")

            # Also broadcast conversation_updated event (for conversation list updates)
            await connection_manager.broadcast_conversation_updated(
                conversation_id=conversation_id,
                updated_by=user_id,
                name=name,
                avatar_url=avatar_url,
                updated_by_name=actor.name if actor else None
            )
        except Exception as ws_error:
            logger.warning(f"WebSocket broadcast failed (non-fatal): {ws_error}")

        # Reload and enrich
        updated_conversation = await self.conversation_repo.get_with_relations(conversation_id)
        return await self._enrich_conversation_with_user_data(updated_conversation, user_id)

    async def add_members(
        self,
        conversation_id: str,
        user_id: str,
        member_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Add members to a conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID (must be admin for groups)
            member_ids: List of user IDs to add

        Returns:
            Success response with count

        Raises:
            HTTPException: If not found or no permission
        """
        # Verify conversation exists
        conversation = await self.conversation_repo.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Cannot add members to DM
        if conversation.type == ConversationType.DM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add members to DM conversation"
            )

        # Verify user is admin
        if not await self.member_repo.is_admin(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can add members"
            )

        # Validate member IDs exist in local database
        from app.models.user import User
        from sqlalchemy import select

        for uid in member_ids:
            result = await self.db.execute(select(User).where(User.id == uid))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {uid} not found"
                )

        # Add members
        added_count = await self.member_repo.add_members(conversation_id, member_ids)
        # CRITICAL FIX: Flush but don't commit yet - system message creation comes first
        await self.db.flush()

        # Create system message and broadcast - BEFORE commit
        try:
            from app.core.websocket import connection_manager
            from app.models.user import User
            from app.services.system_message_service import SystemMessageService
            from sqlalchemy import select
            import logging
            logger = logging.getLogger(__name__)

            logger.info(
                f"[CONVERSATION_SERVICE] 📝 Creating system message for add_members: "
                f"conversation_id={conversation_id}, added_count={added_count}"
            )

            # Get actor (user who added members)
            result = await self.db.execute(select(User).where(User.id == user_id))
            actor = result.scalar_one_or_none()

            # Get added members' details
            added_members_data = []
            for uid in member_ids:
                result = await self.db.execute(select(User).where(User.id == uid))
                added_user = result.scalar_one_or_none()
                if added_user:
                    added_members_data.append({
                        'id': added_user.id,
                        'user_id': added_user.id,
                        'full_name': f"{added_user.first_name} {added_user.last_name}".strip() or added_user.email,
                        'role': 'MEMBER'
                    })

            # Create system message in database
            system_msg = None
            if actor and added_members_data:
                logger.info(f"[CONVERSATION_SERVICE] 📝 Creating system message with actor={actor.email}")
                system_msg = await SystemMessageService.create_member_added_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    actor=actor,
                    added_members=added_members_data
                )
                logger.info(f"[CONVERSATION_SERVICE] ✅ System message created: {system_msg.id}")

            # CRITICAL: Commit transaction AFTER system message is created
            await self.db.commit()
            logger.info(f"[CONVERSATION_SERVICE] ✅ Transaction committed (members + system message)")

            # NOW broadcast (WebSocket failures won't affect database state)
            if system_msg:
                # Convert message to dict for broadcasting
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'sequenceNumber': system_msg.sequence_number,
                    'createdAt': system_msg.created_at.isoformat()
                }

                # Broadcast system message as regular message
                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )
                logger.info(f"[CONVERSATION_SERVICE] ✅ Broadcasted system message")

            # Also broadcast member_added event (for member list updates)
            await connection_manager.broadcast_member_added(
                conversation_id=conversation_id,
                added_members=added_members_data,
                added_by=user_id
            )
            logger.info(f"[CONVERSATION_SERVICE] ✅ Broadcasted member_added event")

        except Exception as error:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"[CONVERSATION_SERVICE] ❌ add_members failed: {type(error).__name__}: {error}",
                exc_info=True
            )
            # Rollback transaction (members + system message)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add members: {str(error)}"
            )

        return {
            "success": True,
            "message": f"Added {added_count} members to conversation",
            "affected_count": added_count
        }

    async def remove_member(
        self,
        conversation_id: str,
        user_id: str,
        member_id: str
    ) -> Dict[str, Any]:
        """
        Remove a member from a conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID (must be admin or removing self)
            member_id: Member UUID to remove

        Returns:
            Success response

        Raises:
            HTTPException: If not found or no permission
        """
        # Verify conversation exists
        conversation = await self.conversation_repo.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Cannot remove members from DM
        if conversation.type == ConversationType.DM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove members from DM conversation"
            )

        # Verify permission (admin or removing self)
        is_admin = await self.member_repo.is_admin(conversation_id, user_id)
        if not is_admin and user_id != member_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can remove other members"
            )

        # Remove member
        removed = await self.member_repo.remove_member(conversation_id, member_id)

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in conversation"
            )

        # CRITICAL FIX: Flush but don't commit yet - system message creation comes first
        await self.db.flush()

        # Create system message and broadcast - BEFORE commit
        try:
            from app.core.websocket import connection_manager
            from app.models.user import User
            from app.services.system_message_service import SystemMessageService
            from sqlalchemy import select
            import logging
            logger = logging.getLogger(__name__)

            logger.info(
                f"[CONVERSATION_SERVICE] 📝 Creating system message for remove_member: "
                f"conversation_id={conversation_id}, member_id={member_id}"
            )

            # Get actor and removed user
            result = await self.db.execute(select(User).where(User.id == user_id))
            actor = result.scalar_one_or_none()

            result = await self.db.execute(select(User).where(User.id == member_id))
            removed_user = result.scalar_one_or_none()

            system_msg = None
            if actor and removed_user:
                logger.info(f"[CONVERSATION_SERVICE] 📝 Creating system message with actor={actor.email}")
                system_msg = await SystemMessageService.create_member_removed_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    actor=actor,
                    removed_user=removed_user
                )
                logger.info(f"[CONVERSATION_SERVICE] ✅ System message created: {system_msg.id}")

            # CRITICAL: Commit transaction AFTER system message is created
            await self.db.commit()
            logger.info(f"[CONVERSATION_SERVICE] ✅ Transaction committed (member removal + system message)")

            # NOW broadcast (WebSocket failures won't affect database state)
            if system_msg:
                # Broadcast as regular message
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'sequenceNumber': system_msg.sequence_number,
                    'createdAt': system_msg.created_at.isoformat()
                }

                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )
                logger.info(f"[CONVERSATION_SERVICE] ✅ Broadcasted system message")

            # Also broadcast member_removed event (for member list updates)
            await connection_manager.broadcast_member_removed(
                conversation_id=conversation_id,
                removed_user_id=member_id,
                removed_by=user_id
            )
            logger.info(f"[CONVERSATION_SERVICE] ✅ Broadcasted member_removed event")

        except Exception as error:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"[CONVERSATION_SERVICE] ❌ remove_member failed: {type(error).__name__}: {error}",
                exc_info=True
            )
            # Rollback transaction (member removal + system message)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove member: {str(error)}"
            )

        return {
            "success": True,
            "message": "Member removed successfully",
            "affected_count": 1
        }

    async def leave_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Leave a conversation.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Success response

        Raises:
            HTTPException: If not found or not a member
        """
        # Verify user is member
        if not await self.member_repo.is_member(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of this conversation"
            )

        # Get user details before leaving (for broadcast)
        from app.models.user import User
        from sqlalchemy import select

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        user_name = f"{user.first_name} {user.last_name}".strip() if user else "Unknown User"
        if not user_name:
            user_name = user.email if user else "Unknown User"

        # Remove member
        await self.member_repo.remove_member(conversation_id, user_id)

        # CRITICAL FIX: Flush but don't commit yet - system message creation comes first
        await self.db.flush()

        # Create system message and broadcast - BEFORE commit
        try:
            from app.core.websocket import connection_manager
            from app.services.system_message_service import SystemMessageService
            import logging
            logger = logging.getLogger(__name__)

            logger.info(
                f"[CONVERSATION_SERVICE] Creating system message for member_left: "
                f"conversation_id={conversation_id}, user_id={user_id}"
            )

            system_msg = None
            if user:
                system_msg = await SystemMessageService.create_member_left_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    user=user
                )
                logger.info(f"[CONVERSATION_SERVICE] System message created: {system_msg.id}")

            # CRITICAL: Commit transaction AFTER system message is created
            await self.db.commit()
            logger.info(f"[CONVERSATION_SERVICE] Transaction committed (member leave + system message)")

            # NOW broadcast (WebSocket failures won't affect database state)
            if system_msg:
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'sequenceNumber': system_msg.sequence_number,
                    'createdAt': system_msg.created_at.isoformat()
                }

                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )
                logger.info(f"[CONVERSATION_SERVICE] Broadcasted system message")

            # Also broadcast member_left event (for member list updates)
            await connection_manager.broadcast_member_left(
                conversation_id=conversation_id,
                user_id=user_id,
                user_name=user_name
            )
        except Exception as error:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"[CONVERSATION_SERVICE] leave_conversation failed: {type(error).__name__}: {error}",
                exc_info=True
            )
            # Rollback transaction (member removal + system message)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to leave conversation: {str(error)}"
            )

        return {
            "success": True,
            "message": "Left conversation successfully"
        }

    async def update_member_settings(
        self,
        conversation_id: str,
        user_id: str,
        is_muted: Optional[bool] = None,
        mute_until: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update conversation settings for user.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            is_muted: Whether to mute notifications
            mute_until: Optional mute expiration

        Returns:
            Updated member settings

        Raises:
            HTTPException: If not found or not a member
        """
        # Verify user is member
        if not await self.member_repo.is_member(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of this conversation"
            )

        # Update mute settings
        if is_muted is not None:
            member = await self.member_repo.update_mute_settings(
                conversation_id,
                user_id,
                is_muted,
                mute_until
            )

            if not member:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update settings"
                )

            await self.db.commit()

            return {
                "success": True,
                "message": "Settings updated successfully",
                "is_muted": member.is_muted,
                "mute_until": member.mute_until
            }

        return {
            "success": False,
            "message": "No settings to update"
        }

    async def mark_conversation_read(
        self,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Mark conversation as read (update last_read_at).

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID

        Returns:
            Success response

        Raises:
            HTTPException: If not found or not a member
        """
        print(f"[MARK_READ] 📖 Marking conversation {conversation_id} as read for user {user_id}")

        # Verify user is member
        if not await self.member_repo.is_member(conversation_id, user_id):
            print(f"[MARK_READ] ❌ User {user_id} is not a member of conversation {conversation_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of this conversation"
            )

        # Update last_read_at
        member = await self.member_repo.update_last_read(conversation_id, user_id)

        if not member:
            print(f"[MARK_READ] ❌ Failed to update last_read_at for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update read status"
            )

        print(f"[MARK_READ] ✅ Updated last_read_at to {member.last_read_at} for user {user_id}")

        await self.db.commit()

        # Invalidate unread count cache (Messenger/Telegram pattern)
        from app.core.cache import invalidate_unread_count_cache, invalidate_total_unread_count_cache
        await invalidate_unread_count_cache(str(user_id), str(conversation_id))
        await invalidate_total_unread_count_cache(str(user_id))
        print(f"[MARK_READ] 🗑️ Invalidated unread count cache for user {user_id}")

        return {
            "success": True,
            "message": "Conversation marked as read",
            "last_read_at": member.last_read_at
        }

    async def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search conversations by name or member names.

        Implements Telegram/Messenger-style fuzzy search with:
        - Trigram similarity for typo tolerance
        - Weighted scoring (60% name, 40% members)
        - Only returns user's conversations

        Args:
            user_id: User UUID
            query: Search query string
            limit: Maximum results (default 20)

        Returns:
            List of enriched conversations ordered by relevance

        Raises:
            HTTPException: If search fails
        """
        try:
            print(f"[SEARCH_SERVICE] 🔍 Starting search for user {str(user_id)[:8]} with query: '{query}'")

            # Search using repository
            conversations = await self.conversation_repo.search_conversations(
                user_id=user_id,
                query=query,
                limit=limit
            )

            print(f"[SEARCH_SERVICE] 📦 Repository returned {len(conversations)} conversations")

            # Enrich conversations with user data
            enriched_conversations = []
            for i, conversation in enumerate(conversations):
                print(f"[SEARCH_SERVICE] 🎨 Enriching conversation {i+1}/{len(conversations)}: {str(conversation.id)[:8]} ({conversation.type})")

                try:
                    enriched = await self._enrich_conversation_with_user_data(
                        conversation=conversation,
                        user_id=user_id
                    )
                    enriched_conversations.append(enriched)
                    print(f"[SEARCH_SERVICE] ✅ Enriched: display_name='{enriched.get('display_name', 'N/A')}', members={len(enriched.get('members', []))}")
                except Exception as enrich_error:
                    print(f"[SEARCH_SERVICE] ❌ Enrichment failed for conversation {str(conversation.id)[:8]}: {str(enrich_error)}")
                    # Continue to next conversation instead of failing entire search
                    continue

            print(f"[SEARCH_SERVICE] 📤 Returning {len(enriched_conversations)} enriched conversations to API")
            return enriched_conversations

        except Exception as e:
            print(f"[SEARCH_SERVICE] ❌ Search failed with error: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to search conversations: {str(e)}"
            )
