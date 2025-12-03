"""
Conversation API routes.
Provides endpoints for creating, retrieving, and managing conversations.
"""
from typing import Optional
# UUID import removed - using str for ID types

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
    - **member_ids**: List of TMS user IDs to add as members
    """
    from app.models.user import User
    from app.repositories.user_repo import UserRepository
    from app.core.tms_client import tms_client
    from sqlalchemy import select
    # UUID import removed - using str for ID types

    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)
    user_repo = UserRepository(db)

    # Validate: current user should NOT be in member_ids (they're added automatically as creator/admin)
    current_user_tms_id = current_user.get("tms_user_id")
    if current_user_tms_id in conversation_data.member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are automatically added as the conversation creator/admin. Do not include yourself in member_ids."
        )

    # Convert TMS user IDs to local database IDs
    local_member_ids: list[str] = []

    for tms_user_id in conversation_data.member_ids:

        # Check if user exists locally
        result = await db.execute(
            select(User).where(User.tms_user_id == tms_user_id)
        )
        local_user = result.scalar_one_or_none()

        if not local_user:
            # Fetch user from TMS and sync to local database
            try:
                tms_user_data = await tms_client.get_user_by_id_with_api_key(
                    user_id=tms_user_id,
                    use_cache=True
                )

                # Sync user to local database
                local_user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
                await db.commit()

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch user {tms_user_id} from Team Management System: {str(e)}"
                )

        local_member_ids.append(local_user.id)

    # Create conversation with local UUIDs
    conversation = await service.create_conversation(
        creator_id=user.id,
        type=conversation_data.type,
        member_ids=local_member_ids,
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
    cursor: Optional[str] = Query(None, description="Cursor for pagination (last conversation ID)"),
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
    "/search",
    response_model=ConversationListResponse,
    summary="Search conversations",
    description="Search conversations by name or member names using fuzzy matching (Telegram/Messenger style)."
)
async def search_conversations(
    q: str = Query(..., min_length=1, max_length=100, description="Search query (conversation or member name)"),
    limit: int = Query(default=20, ge=1, le=50, description="Number of results to return"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search conversations by name or member names.

    Implements Telegram/Messenger-style search:
    - Fuzzy matching for typo tolerance
    - Searches conversation names (60% weight)
    - Searches member names (40% weight)
    - Returns only conversations the user is a member of
    - Results ordered by relevance

    - **q**: Search query string (min 1 char)
    - **limit**: Maximum results (max 50)
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    conversations = await service.search_conversations(
        user_id=user.id,
        query=q,
        limit=limit
    )

    return {
        "data": conversations,
        "pagination": {
            "next_cursor": None,  # Search doesn't use cursor pagination
            "has_more": len(conversations) >= limit,
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
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single conversation by its ID.

    - **conversation_id**: ID of the conversation to retrieve
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
    conversation_id: str,
    conversation_data: ConversationUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation details.

    - **conversation_id**: ID of the conversation to update
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
    conversation_id: str,
    member_data: ConversationMemberAdd,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add members to a conversation.

    - **conversation_id**: ID of the conversation
    - **user_ids**: List of TMS user IDs to add
    """
    from app.models.user import User
    from app.repositories.user_repo import UserRepository
    from app.core.tms_client import tms_client
    from sqlalchemy import select

    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)
    user_repo = UserRepository(db)

    # Convert TMS user IDs to local database IDs
    local_member_ids: list[str] = []

    for tms_user_id in member_data.user_ids:
        # Check if user exists locally
        result = await db.execute(
            select(User).where(User.tms_user_id == tms_user_id)
        )
        local_user = result.scalar_one_or_none()

        if not local_user:
            # Fetch user from TMS and sync to local database
            try:
                tms_user_data = await tms_client.get_user_by_id_with_api_key(
                    user_id=tms_user_id,
                    use_cache=True
                )

                # Sync user to local database
                local_user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
                await db.commit()

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch user {tms_user_id} from Team Management System: {str(e)}"
                )

        local_member_ids.append(local_user.id)

    # Add members using local UUIDs
    result = await service.add_members(
        conversation_id=conversation_id,
        user_id=user.id,
        member_ids=local_member_ids
    )

    return result


@router.delete(
    "/{conversation_id}/members/{member_id}",
    response_model=ConversationMemberUpdateResponse,
    summary="Remove a member from conversation",
    description="Remove a member from a group conversation. Admins can remove others, or users can remove themselves."
)
async def remove_member(
    conversation_id: str,
    member_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a conversation.

    - **conversation_id**: ID of the conversation
    - **member_id**: ID of the member to remove
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
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Leave a conversation.

    - **conversation_id**: ID of the conversation to leave
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
    conversation_id: str,
    settings_data: ConversationSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation notification settings.

    - **conversation_id**: ID of the conversation
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
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark conversation as read.

    - **conversation_id**: ID of the conversation
    """
    service = ConversationService(db)
    user = await get_current_user_from_db(current_user, db)

    result = await service.mark_conversation_read(
        conversation_id=conversation_id,
        user_id=user.id
    )

    return result


# MOVED TO LINE 156 - must come before /{conversation_id} route
