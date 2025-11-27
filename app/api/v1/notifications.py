"""
Notification API endpoints.
Provides notification preferences and muted conversation management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.services.notification_service import NotificationService
from app.schemas.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    MutedConversationBase,
    MutedConversationResponse,
    MutedConversationListResponse
)

router = APIRouter()


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's notification preferences.

    Creates default preferences if they don't exist.

    **Authentication**: Required

    **Returns**: NotificationPreferencesResponse
    """
    notification_service = NotificationService(db)

    try:
        preferences = await notification_service.get_or_create_preferences(
            user_id=str(current_user["id"])
        )
        return preferences
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification preferences: {str(e)}"
        )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    updates: NotificationPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's notification preferences.

    Only provided fields will be updated. All fields are optional.

    **Authentication**: Required

    **Request Body**:
    - `sound_enabled` (bool, optional): Enable/disable sound notifications
    - `sound_volume` (int, optional): Volume level (0-100)
    - `browser_notifications_enabled` (bool, optional): Enable/disable browser notifications
    - `enable_message_notifications` (bool, optional): Enable/disable message notifications
    - `enable_mention_notifications` (bool, optional): Enable/disable @mention notifications
    - `enable_reaction_notifications` (bool, optional): Enable/disable reaction notifications
    - `enable_member_activity_notifications` (bool, optional): Enable/disable member activity notifications
    - `dnd_enabled` (bool, optional): Enable/disable Do Not Disturb mode
    - `dnd_start` (str, optional): DND start time (HH:MM format, e.g., "22:00")
    - `dnd_end` (str, optional): DND end time (HH:MM format, e.g., "08:00")

    **Returns**: Updated NotificationPreferencesResponse
    """
    notification_service = NotificationService(db)

    try:
        preferences = await notification_service.update_preferences(
            user_id=str(current_user["id"]),
            updates=updates
        )
        return preferences
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification preferences: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/mute", response_model=MutedConversationResponse)
async def mute_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mute a conversation for the current user.

    Muted conversations won't generate notifications (except @mentions).

    **Authentication**: Required

    **Parameters**:
    - `conversation_id`: ID of the conversation to mute

    **Returns**: MutedConversationResponse
    """
    notification_service = NotificationService(db)

    try:
        muted = await notification_service.mute_conversation(
            user_id=str(current_user["id"]),
            conversation_id=conversation_id
        )
        return muted
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mute conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}/mute", status_code=status.HTTP_204_NO_CONTENT)
async def unmute_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unmute a conversation for the current user.

    **Authentication**: Required

    **Parameters**:
    - `conversation_id`: ID of the conversation to unmute

    **Returns**: HTTP 204 No Content on success
    """
    notification_service = NotificationService(db)

    try:
        was_muted = await notification_service.unmute_conversation(
            user_id=str(current_user["id"]),
            conversation_id=conversation_id
        )

        if not was_muted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation was not muted"
            )

        return None  # 204 No Content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unmute conversation: {str(e)}"
        )


@router.get("/muted-conversations", response_model=MutedConversationListResponse)
async def get_muted_conversations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all muted conversations for the current user.

    **Authentication**: Required

    **Returns**: List of muted conversations with total count
    """
    notification_service = NotificationService(db)

    try:
        muted_conversations = await notification_service.get_muted_conversations(
            user_id=str(current_user["id"])
        )
        return muted_conversations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get muted conversations: {str(e)}"
        )
