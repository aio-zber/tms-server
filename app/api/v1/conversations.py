"""
Conversation API routes.
Provides endpoints for creating, retrieving, and managing conversations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    ConversationMemberAdd,
    ConversationSettingsUpdate,
    ConversationDeleteResponse,
    ConversationMemberUpdateResponse
)
from app.services.conversation_service import ConversationService

router = APIRouter()


async def get_current_user_from_db(current_user: dict, db: AsyncSession):
    """Helper to get local user from TMS user."""
    from app.models.user import User
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.tms_user_id == current_user["tms_user_id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in local database"
        )

    return user


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    description="Create a new DM or group conversation with specified members."
)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation.

    - **type**: Conversation type ('dm' or 'group')
    - **name**: Conversation name (required for groups)
    - **avatar_url**: Optional avatar URL
    - **member_ids**: List of user IDs to add as members
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    conversation = await service.create_conversation(
        creator_id=user.id,
        type=conversation_data.type,
        member_ids=conversation_data.member_ids,
        name=conversation_data.name,
        avatar_url=conversation_data.avatar_url
    )

    return conversation


@router.get(
    "/",
    response_model=ConversationListResponse,
    summary="Get user's conversations",
    description="Get all conversations for the current user with cursor-based pagination."
)
async def get_user_conversations(
    limit: int = Query(default=50, ge=1, le=100, description="Number of conversations to return"),
    cursor: Optional[UUID] = Query(None, description="Cursor for pagination (last conversation ID)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all conversations for the current user.

    - **limit**: Number of conversations (max 100)
    - **cursor**: Last conversation ID for pagination
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    conversations, next_cursor, has_more = await service.get_user_conversations(
        user_id=user.id,
        limit=limit,
        cursor=cursor
    )

    return {
        "data": conversations,
        "pagination": {
            "next_cursor": str(next_cursor) if next_cursor else None,
            "has_more": has_more,
            "limit": limit
        }
    }


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a conversation by ID",
    description="Retrieve a single conversation with all its details including members."
)
async def get_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single conversation by its ID.

    - **conversation_id**: UUID of the conversation to retrieve
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    conversation = await service.get_conversation(conversation_id, user.id)
    return conversation


@router.put(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation details",
    description="Update conversation name or avatar. Only admins can update group conversations."
)
async def update_conversation(
    conversation_id: UUID,
    conversation_data: ConversationUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation details.

    - **conversation_id**: UUID of the conversation to update
    - **name**: Updated conversation name
    - **avatar_url**: Updated avatar URL
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    conversation = await service.update_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
        name=conversation_data.name,
        avatar_url=conversation_data.avatar_url
    )

    return conversation


@router.post(
    "/{conversation_id}/members",
    response_model=ConversationMemberUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Add members to conversation",
    description="Add new members to a group conversation. Only admins can add members."
)
async def add_members(
    conversation_id: UUID,
    member_data: ConversationMemberAdd,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add members to a conversation.

    - **conversation_id**: UUID of the conversation
    - **user_ids**: List of user IDs to add
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.add_members(
        conversation_id=conversation_id,
        user_id=user.id,
        member_ids=member_data.user_ids
    )

    return result


@router.delete(
    "/{conversation_id}/members/{member_id}",
    response_model=ConversationMemberUpdateResponse,
    summary="Remove a member from conversation",
    description="Remove a member from a group conversation. Admins can remove others, or users can remove themselves."
)
async def remove_member(
    conversation_id: UUID,
    member_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a conversation.

    - **conversation_id**: UUID of the conversation
    - **member_id**: UUID of the member to remove
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.remove_member(
        conversation_id=conversation_id,
        user_id=user.id,
        member_id=member_id
    )

    return result


@router.post(
    "/{conversation_id}/leave",
    response_model=ConversationMemberUpdateResponse,
    summary="Leave a conversation",
    description="Remove yourself from a conversation."
)
async def leave_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Leave a conversation.

    - **conversation_id**: UUID of the conversation to leave
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.leave_conversation(
        conversation_id=conversation_id,
        user_id=user.id
    )

    return result


@router.put(
    "/{conversation_id}/settings",
    response_model=dict,
    summary="Update conversation settings",
    description="Update notification settings for a conversation (mute/unmute)."
)
async def update_conversation_settings(
    conversation_id: UUID,
    settings_data: ConversationSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation notification settings.

    - **conversation_id**: UUID of the conversation
    - **is_muted**: Whether to mute notifications
    - **mute_until**: Optional mute expiration datetime
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.update_member_settings(
        conversation_id=conversation_id,
        user_id=user.id,
        is_muted=settings_data.is_muted,
        mute_until=settings_data.mute_until
    )

    return result


@router.post(
    "/{conversation_id}/mark-read",
    response_model=dict,
    summary="Mark conversation as read",
    description="Update last_read_at timestamp to mark all messages as read."
)
async def mark_conversation_read(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark conversation as read.

    - **conversation_id**: UUID of the conversation
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.mark_conversation_read(
        conversation_id=conversation_id,
        user_id=user.id
    )

    return result
