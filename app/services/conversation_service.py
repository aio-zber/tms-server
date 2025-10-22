"""
Conversation service containing business logic for conversation operations.
Handles conversation CRUD, member management, and integrations.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

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
        user_id: UUID
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
                    creator_data = await tms_client.get_user(
                        creator.tms_user_id,
                        use_cache=True
                    )
                    conversation_dict["creator"] = creator_data
            except (TMSAPIException, Exception):
                # Fallback to basic creator info
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

            # Fetch user data from TMS
            if member.user:
                try:
                    print(f"[CONVERSATION_SERVICE] Fetching TMS user data for: {member.user.tms_user_id}")
                    # Use API Key authentication for server-to-server calls (PREFERRED METHOD)
                    user_data = await tms_client.get_user_by_id_with_api_key(
                        member.user.tms_user_id,
                        use_cache=True
                    )
                    print(f"[CONVERSATION_SERVICE] ✅ Got TMS user data: {user_data.get('email', 'N/A')}")
                    member_dict["user"] = user_data
                except TMSAPIException as e:
                    # Fallback to basic user info
                    print(f"[CONVERSATION_SERVICE] ❌ TMS API failed: {str(e)}")
                    member_dict["user"] = {
                        "id": str(member.user_id),
                        "tms_user_id": member.user.tms_user_id
                    }
                except Exception as e:
                    # Catch all other exceptions
                    print(f"[CONVERSATION_SERVICE] ❌ Unexpected error: {type(e).__name__}: {str(e)}")
                    member_dict["user"] = {
                        "id": str(member.user_id),
                        "tms_user_id": member.user.tms_user_id
                    }

            enriched_members.append(member_dict)

        conversation_dict["members"] = enriched_members
        conversation_dict["member_count"] = len(enriched_members)

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
                "timestamp": last_message.created_at  # Frontend expects "timestamp"
            }

        return conversation_dict

    async def create_conversation(
        self,
        creator_id: UUID,
        type: ConversationType,
        member_ids: List[UUID],
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            creator_id: Creator user UUID
            type: Conversation type (dm/group)
            member_ids: List of member user IDs
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

        # Validate all member IDs exist in local database
        from app.models.user import User
        from sqlalchemy import select

        all_member_ids = [creator_id] + [uid for uid in member_ids if uid != creator_id]

        for uid in all_member_ids:
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
        conversation_id: UUID,
        user_id: UUID
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
        user_id: UUID,
        limit: int = 50,
        cursor: Optional[UUID] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[UUID], bool]:
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
        conversation_id: UUID,
        user_id: UUID,
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

        await self.db.commit()

        # Reload and enrich
        updated_conversation = await self.conversation_repo.get_with_relations(conversation_id)
        return await self._enrich_conversation_with_user_data(updated_conversation, user_id)

    async def add_members(
        self,
        conversation_id: UUID,
        user_id: UUID,
        member_ids: List[UUID]
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
        await self.db.commit()

        return {
            "success": True,
            "message": f"Added {added_count} members to conversation",
            "affected_count": added_count
        }

    async def remove_member(
        self,
        conversation_id: UUID,
        user_id: UUID,
        member_id: UUID
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

        await self.db.commit()

        return {
            "success": True,
            "message": "Member removed successfully",
            "affected_count": 1
        }

    async def leave_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID
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

        # Remove member
        await self.member_repo.remove_member(conversation_id, user_id)
        await self.db.commit()

        return {
            "success": True,
            "message": "Left conversation successfully"
        }

    async def update_member_settings(
        self,
        conversation_id: UUID,
        user_id: UUID,
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
        conversation_id: UUID,
        user_id: UUID
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
        user_id: UUID,
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
            # Search using repository
            conversations = await self.conversation_repo.search_conversations(
                user_id=user_id,
                query=query,
                limit=limit
            )

            # Enrich conversations with user data
            enriched_conversations = []
            for conversation in conversations:
                enriched = await self._enrich_conversation_with_user_data(
                    conversation=conversation,
                    user_id=user_id
                )
                enriched_conversations.append(enriched)

            return enriched_conversations

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to search conversations: {str(e)}"
            )
