"""
Poll API routes.
Provides endpoints for creating polls, voting, and managing poll results.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.poll import (
    PollCreate,
    PollVoteCreate,
    PollResponse,
    PollVoteResponse,
    CreatePollResponse
)
from app.services.poll_service import PollService
from app.core.websocket import connection_manager

router = APIRouter()


@router.post(
    "/",
    response_model=CreatePollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new poll",
    description="Create a new poll attached to a message in a conversation."
)
async def create_poll(
    poll_data: PollCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new poll.

    - **conversation_id**: ID of the conversation
    - **question**: Poll question (1-255 characters)
    - **options**: List of 2-10 poll options
    - **multiple_choice**: Allow multiple answers (default: False)
    - **expires_at**: Optional expiration datetime
    """
    try:
        service = PollService(db)

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

        # Create poll
        result = await service.create_poll(
            user_id=user.id,
            conversation_id=poll_data.conversation_id,
            question=poll_data.question,
            options=[{"option_text": opt.option_text, "position": opt.position} for opt in poll_data.options],
            multiple_choice=poll_data.multiple_choice,
            expires_at=poll_data.expires_at
        )

        # Broadcast poll creation via WebSocket
        try:
            # Convert UUIDs to strings for JSON serialization
            def convert_uuids(obj):
                """Recursively convert UUID objects to strings."""
                from datetime import datetime
                if isinstance(obj, dict):
                    return {k: convert_uuids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids(item) for item in obj]
                elif isinstance(obj, UUID):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            broadcast_data = convert_uuids(result)

            await connection_manager.broadcast_new_poll(
                poll_data.conversation_id,
                broadcast_data
            )
        except Exception as e:
            print(f"[POLLS] Failed to broadcast poll creation: {e}")
            # Don't fail the request if broadcast fails

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [POLL] Failed to create poll: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create poll: {str(e)}"
        )


@router.post(
    "/{poll_id}/vote",
    response_model=PollVoteResponse,
    summary="Vote on a poll",
    description="Cast or update vote on a poll."
)
async def vote_on_poll(
    poll_id: str,
    vote_data: PollVoteCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Vote on a poll.

    - **poll_id**: ID of the poll
    - **option_ids**: List of option UUID(s) to vote for

    For single-choice polls: Replaces existing vote
    For multiple-choice polls: Toggles votes on specified options
    """
    import logging
    logger = logging.getLogger(__name__)

    service = PollService(db)

    try:
        # Get user_id from local user record
        from app.models.user import User
        from sqlalchemy import select

        result = await db.execute(
            select(User).where(User.tms_user_id == current_user["tms_user_id"])
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"[POLLS] User not found: tms_user_id={current_user.get('tms_user_id')}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in local database"
            )

        logger.info(f"[POLLS] Vote request: poll_id={poll_id}, user_id={user.id}, option_ids={vote_data.option_ids}")

        # Vote on poll
        poll_response = await service.vote_on_poll(
            poll_id=poll_id,
            user_id=user.id,
            option_ids=vote_data.option_ids
        )

        logger.info(f"[POLLS] ✅ Vote successful: poll_id={poll_id}, user_id={user.id}")

    except HTTPException:
        # Re-raise HTTP exceptions (already have proper status codes)
        raise
    except Exception as error:
        logger.error(
            f"[POLLS] ❌ Vote failed: poll_id={poll_id}, user_id={user.id if 'user' in locals() else 'unknown'}, "
            f"error={type(error).__name__}: {str(error)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to vote on poll: {str(error)}"
        )

    # Get conversation_id for WebSocket broadcast
    from app.models.poll import Poll
    from app.models.message import Message

    result = await db.execute(
        select(Message.conversation_id)
        .join(Poll, Message.id == Poll.message_id)
        .where(Poll.id == poll_id)
    )
    conversation_id = result.scalar_one_or_none()

    # Broadcast vote update via WebSocket
    if conversation_id:
        try:
            # Convert UUIDs to strings for JSON serialization
            def convert_uuids(obj):
                """Recursively convert UUID objects to strings."""
                from datetime import datetime
                if isinstance(obj, dict):
                    return {k: convert_uuids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids(item) for item in obj]
                elif isinstance(obj, UUID):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            broadcast_data = {
                "poll_id": str(poll_id),
                "user_id": str(user.id),
                "poll": convert_uuids(poll_response.model_dump(by_alias=True, mode='json'))
            }

            await connection_manager.broadcast_poll_vote(
                conversation_id,
                broadcast_data
            )
        except Exception as e:
            print(f"[POLLS] Failed to broadcast vote: {e}")
            # Don't fail the request if broadcast fails

    return PollVoteResponse(
        success=True,
        poll=poll_response,
        message="Vote recorded successfully"
    )


@router.put(
    "/{poll_id}/close",
    response_model=PollResponse,
    summary="Close a poll",
    description="Close a poll early (only poll creator can close)."
)
async def close_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Close a poll early.

    Only the poll creator can close the poll.

    - **poll_id**: ID of the poll
    """
    service = PollService(db)

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

    # Close poll
    poll_response = await service.close_poll(poll_id, user.id)

    # Get conversation_id for WebSocket broadcast
    from app.models.poll import Poll
    from app.models.message import Message

    result = await db.execute(
        select(Message.conversation_id)
        .join(Poll, Message.id == Poll.message_id)
        .where(Poll.id == poll_id)
    )
    conversation_id = result.scalar_one_or_none()

    # Broadcast poll closed via WebSocket
    if conversation_id:
        try:
            # Convert UUIDs to strings for JSON serialization
            def convert_uuids(obj):
                """Recursively convert UUID objects to strings."""
                from datetime import datetime
                if isinstance(obj, dict):
                    return {k: convert_uuids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids(item) for item in obj]
                elif isinstance(obj, UUID):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            broadcast_data = {
                "poll_id": str(poll_id),
                "poll": convert_uuids(poll_response)
            }

            await connection_manager.broadcast_poll_closed(
                conversation_id,
                broadcast_data
            )
        except Exception as e:
            print(f"[POLLS] Failed to broadcast poll closed: {e}")
            # Don't fail the request if broadcast fails

    return poll_response


@router.get(
    "/{poll_id}",
    response_model=PollResponse,
    summary="Get poll details",
    description="Get poll details with results."
)
async def get_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get poll details with vote counts and results.

    - **poll_id**: ID of the poll
    """
    service = PollService(db)

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

    return await service.get_poll(poll_id, user.id)
