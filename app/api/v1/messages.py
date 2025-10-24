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
    try:
        service = MessageService(db)

        # Get user_id from local user record
        from app.models.user import User
        from sqlalchemy import select
        from sqlalchemy.exc import SQLAlchemyError

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
    except HTTPException:
        # Re-raise FastAPI HTTP exceptions
        raise
    except SQLAlchemyError as e:
        # Log database errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"Database error fetching messages: {type(e).__name__}: {str(e)}",
            extra={
                "user_id": current_user.get("tms_user_id"),
                "conversation_id": str(conversation_id),
                "cursor": str(cursor) if cursor else None,
                "limit": limit
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while fetching messages. Please try again."
        )
    except Exception as e:
        # Log unexpected errors
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(
            f"Unexpected error fetching messages: {type(e).__name__}: {str(e)}",
            extra={
                "user_id": current_user.get("tms_user_id"),
                "conversation_id": str(conversation_id),
                "cursor": str(cursor) if cursor else None,
                "limit": limit,
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching messages: {type(e).__name__}"
        )

    # Debug: Check reply_to data
    print(f"[API] Fetched {len(messages)} messages")
    for msg in messages:
        if msg.get('reply_to_id'):
            print(f"[API] Message {msg['id']} has reply_to_id: {msg['reply_to_id']}")
            print(f"[API] Message reply_to object present: {msg.get('reply_to') is not None}")
            if msg.get('reply_to'):
                print(f"[API] reply_to data: {msg['reply_to'].keys() if isinstance(msg['reply_to'], dict) else 'not a dict'}")

    # Convert enriched dict messages to Pydantic models for proper serialization
    # Need to handle nested reply_to manually since Pydantic doesn't auto-convert nested dicts
    message_responses = []
    for msg in messages:
        # Convert nested reply_to dict to MessageResponse if present
        if msg.get('reply_to'):
            print(f"[API] Converting reply_to for message {msg['id']}")
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
    import logging
    import traceback
    logger = logging.getLogger(__name__)

    try:
        # LOG: Incoming request
        logger.info(
            f"[MARK_READ] 📬 Incoming request: "
            f"user={current_user.get('tms_user_id', 'unknown')}, "
            f"conversation_id={request_data.conversation_id}, "
            f"message_count={len(request_data.message_ids)}, "
            f"message_ids={[str(mid)[:8] + '...' for mid in request_data.message_ids[:5]]}"
        )

        service = MessageService(db)

        # LOG: User lookup
        logger.info(f"[MARK_READ] 🔍 Looking up user: tms_user_id={current_user['tms_user_id']}")

        # Get user_id from local user record
        from app.models.user import User
        from sqlalchemy import select

        result = await db.execute(
            select(User).where(User.tms_user_id == current_user["tms_user_id"])
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.error(
                f"[MARK_READ] ❌ User not found in local database: "
                f"tms_user_id={current_user['tms_user_id']}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in local database"
            )

        logger.info(
            f"[MARK_READ] ✅ User found: "
            f"local_id={user.id}, email={user.email}, name={user.first_name} {user.last_name}"
        )

        # LOG: Service call
        logger.info(
            f"[MARK_READ] 🚀 Calling service.mark_messages_read: "
            f"user_id={user.id}, conversation_id={request_data.conversation_id}"
        )

        result = await service.mark_messages_read(
            message_ids=request_data.message_ids,
            user_id=user.id,
            conversation_id=request_data.conversation_id
        )

        logger.info(
            f"[MARK_READ] ✅ Success: updated_count={result['updated_count']}, "
            f"success={result['success']}"
        )

        return result

    except HTTPException:
        # Re-raise HTTP exceptions (already logged above)
        raise
    except Exception as e:
        # LOG: Unexpected errors with full traceback
        error_traceback = traceback.format_exc()
        logger.error(
            f"[MARK_READ] ❌ UNEXPECTED ERROR: {type(e).__name__}: {str(e)}\n"
            f"Request data: conversation_id={request_data.conversation_id}, "
            f"message_ids={request_data.message_ids}\n"
            f"User: {current_user.get('tms_user_id')}\n"
            f"Traceback:\n{error_traceback}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark messages as read: {type(e).__name__}: {str(e)}"
        )


@router.post(
    "/mark-delivered",
    response_model=MessageStatusUpdateResponse,
    summary="Mark messages as delivered",
    description="Mark all undelivered messages in a conversation as delivered (Telegram/Messenger pattern)."
)
async def mark_messages_delivered(
    request_data: MessageMarkReadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark messages as delivered when user opens conversation.

    Implements Telegram/Messenger pattern:
    - Automatically called when conversation is opened
    - Marks all SENT messages as DELIVERED
    - Does not affect READ messages

    - **conversation_id**: UUID of the conversation
    - **message_ids**: Optional list of specific message UUIDs (if empty, marks all SENT messages)
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

    result = await service.mark_messages_delivered(
        conversation_id=request_data.conversation_id,
        user_id=user.id,
        message_ids=request_data.message_ids if request_data.message_ids else None
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

    Uses last_read_at timestamp for accurate counting (Telegram/Messenger pattern).

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

    # Use ConversationMemberRepository with last_read_at timestamp (more reliable)
    from app.repositories.conversation_repo import ConversationMemberRepository
    member_repo = ConversationMemberRepository(db)
    count = await member_repo.get_unread_count(conversation_id, user.id)

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

    Uses last_read_at timestamp for accurate counting (Telegram/Messenger pattern).

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
    from app.repositories.conversation_repo import ConversationMemberRepository

    result = await db.execute(
        select(ConversationMember.conversation_id)
        .where(ConversationMember.user_id == user.id)
    )
    conversation_ids = [row[0] for row in result.all()]

    # Get unread count for each conversation using last_read_at timestamp
    member_repo = ConversationMemberRepository(db)
    conversation_counts = {}
    total_count = 0

    for conversation_id in conversation_ids:
        count = await member_repo.get_unread_count(conversation_id, user.id)
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
