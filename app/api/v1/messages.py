"""
Message API routes.
Provides endpoints for sending, retrieving, editing, and managing messages.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.dependencies import get_current_user, get_pagination_params
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
    MessageReactionCreate,
    MessageMarkReadRequest,
    MessageSearchRequest,
    MessageStatusUpdateResponse,
    MessageDeleteResponse,
    MessageReactionResponse
)
from app.services.message_service import MessageService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a new message",
    description="Send a new message to a conversation. User must be a member of the conversation."
)
@limiter.limit("30/minute")  # Max 30 messages per minute per user
async def send_message(
    request: Request,
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a new message to a conversation.

    - **conversation_id**: UUID of the conversation
    - **content**: Message text content (required for text messages)
    - **type**: Message type (text, image, file, voice, poll, call)
    - **metadata_json**: Additional metadata (URLs, dimensions, etc.)
    - **reply_to_id**: Optional UUID of message being replied to
    """
    try:
        service = MessageService(db)

        # Get user_id from local user record
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

        message = await service.send_message(
            sender_id=user.id,
            conversation_id=message_data.conversation_id,
            content=message_data.content,
            message_type=message_data.type,
            metadata_json=message_data.metadata_json,
            reply_to_id=message_data.reply_to_id
        )

        return message
    except Exception as e:
        # Log the full error
        import traceback
        print(f"❌ ERROR sending message: {type(e).__name__}: {str(e)}")
        print(traceback.format_exc())
        
        # Re-raise with more details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {type(e).__name__}: {str(e)}"
        )


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get a message by ID",
    description="Retrieve a single message with all its details including reactions and status."
)
async def get_message(
    message_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single message by its ID.

    - **message_id**: UUID of the message to retrieve
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    message = await service.get_message(message_id, user.id)
    return message


@router.put(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Edit a message",
    description="Edit the content of a message. Only the sender can edit their own messages."
)
async def edit_message(
    message_id: UUID,
    message_data: MessageUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Edit a message's content.

    - **message_id**: UUID of the message to edit
    - **content**: New message content
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    message = await service.edit_message(
        message_id=message_id,
        user_id=user.id,
        new_content=message_data.content
    )

    return message


@router.delete(
    "/{message_id}",
    response_model=MessageDeleteResponse,
    summary="Delete a message",
    description="Soft delete a message. Only the sender can delete their own messages."
)
async def delete_message(
    message_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a message (soft delete).

    - **message_id**: UUID of the message to delete
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    result = await service.delete_message(message_id, user.id)
    return result


@router.post(
    "/{message_id}/reactions",
    response_model=MessageReactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a reaction to a message",
    description="Add an emoji reaction to a message."
)
@limiter.limit("60/minute")  # Max 60 reactions per minute
async def add_reaction(
    request: Request,
    message_id: UUID,
    reaction_data: MessageReactionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a reaction to a message.

    - **message_id**: UUID of the message
    - **emoji**: Emoji to react with
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    reaction = await service.add_reaction(
        message_id=message_id,
        user_id=user.id,
        emoji=reaction_data.emoji
    )

    return reaction


@router.delete(
    "/{message_id}/reactions/{emoji}",
    response_model=dict,
    summary="Remove a reaction from a message",
    description="Remove an emoji reaction from a message."
)
async def remove_reaction(
    message_id: UUID,
    emoji: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a reaction from a message.

    - **message_id**: UUID of the message
    - **emoji**: Emoji to remove
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    result = await service.remove_reaction(
        message_id=message_id,
        user_id=user.id,
        emoji=emoji
    )

    return result


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="Get conversation messages",
    description="Get paginated messages for a conversation with cursor-based pagination."
)
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(default=10, ge=1, le=100, description="Number of messages to return"),
    cursor: Optional[UUID] = Query(None, description="Cursor for pagination (last message ID)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a conversation with pagination.

    - **conversation_id**: UUID of the conversation
    - **limit**: Number of messages (max 100)
    - **cursor**: Last message ID for pagination
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    messages, next_cursor, has_more = await service.get_conversation_messages(
        conversation_id=conversation_id,
        user_id=user.id,
        limit=limit,
        cursor=cursor
    )

    # Convert enriched dict messages to Pydantic models for proper serialization
    # Need to handle nested reply_to manually since Pydantic doesn't auto-convert nested dicts
    message_responses = []
    for msg in messages:
        # Convert nested reply_to dict to MessageResponse if present
        if msg.get('reply_to'):
            msg['reply_to'] = MessageResponse(**msg['reply_to'])
        message_responses.append(MessageResponse(**msg))

    return MessageListResponse(
        data=message_responses,
        pagination={
            "next_cursor": str(next_cursor) if next_cursor else None,
            "has_more": has_more,
            "limit": limit
        }
    )


@router.post(
    "/mark-read",
    response_model=MessageStatusUpdateResponse,
    summary="Mark messages as read",
    description="Mark multiple messages as read in a conversation."
)
async def mark_messages_read(
    request_data: MessageMarkReadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark multiple messages as read.

    - **message_ids**: List of message UUIDs to mark as read
    - **conversation_id**: UUID of the conversation
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    result = await service.mark_messages_read(
        message_ids=request_data.message_ids,
        user_id=user.id,
        conversation_id=request_data.conversation_id
    )

    return result


@router.get(
    "/conversations/{conversation_id}/unread-count",
    response_model=dict,
    summary="Get unread message count for a conversation",
    description="Get the number of unread messages in a specific conversation."
)
async def get_conversation_unread_count(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unread message count for a conversation.

    - **conversation_id**: UUID of the conversation
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    # Use repository method directly
    from app.repositories.message_repo import MessageRepository
    message_repo = MessageRepository(db)
    count = await message_repo.get_unread_count(user.id, conversation_id)

    return {
        "conversation_id": str(conversation_id),
        "unread_count": count
    }


@router.get(
    "/unread-count",
    response_model=dict,
    summary="Get total unread message count",
    description="Get the total number of unread messages across all conversations."
)
async def get_total_unread_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get total unread message count across all conversations.

    Returns the total count and per-conversation breakdown.
    """
    # Get user_id from local user record
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

    # Get all conversations the user is part of
    from app.models.conversation import ConversationMember
    from app.repositories.message_repo import MessageRepository

    result = await db.execute(
        select(ConversationMember.conversation_id)
        .where(ConversationMember.user_id == user.id)
    )
    conversation_ids = [row[0] for row in result.all()]

    # Get unread count for each conversation
    message_repo = MessageRepository(db)
    conversation_counts = {}
    total_count = 0

    for conversation_id in conversation_ids:
        count = await message_repo.get_unread_count(user.id, conversation_id)
        if count > 0:
            conversation_counts[str(conversation_id)] = count
            total_count += count

    return {
        "total_unread_count": total_count,
        "conversations": conversation_counts
    }


@router.post(
    "/search",
    response_model=MessageListResponse,
    summary="Search messages",
    description="Search messages with filters (query, conversation, sender, date range)."
)
async def search_messages(
    search_data: MessageSearchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search messages with various filters.

    - **query**: Search query string
    - **conversation_id**: Optional conversation filter
    - **sender_id**: Optional sender filter
    - **message_type**: Optional message type filter
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    - **limit**: Number of results (max 100)
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    messages = await service.search_messages(
        query=search_data.query,
        user_id=user.id,
        conversation_id=search_data.conversation_id,
        sender_id=search_data.sender_id,
        start_date=search_data.start_date,
        end_date=search_data.end_date,
        limit=search_data.limit
    )

    return {
        "data": messages,
        "pagination": {
            "total": len(messages),
            "limit": search_data.limit,
            "has_more": len(messages) >= search_data.limit
        }
    }


@router.delete(
    "/conversations/{conversation_id}/clear",
    response_model=dict,
    summary="Clear conversation messages",
    description="Soft delete all messages in a conversation for the current user."
)
async def clear_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear all messages in a conversation (soft delete).

    - **conversation_id**: UUID of the conversation
    """
    service = MessageService(db)

    # Get user_id from local user record
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

    deleted_count = await service.clear_conversation(
        conversation_id=conversation_id,
        user_id=user.id
    )

    return {
        "success": True,
        "message": f"Cleared {deleted_count} messages from conversation",
        "deleted_count": deleted_count
    }
