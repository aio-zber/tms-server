"""
Poll service containing business logic for poll operations.
Handles poll creation, voting, closing, and results retrieval.
"""
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
# UUID import removed - using str for ID types

from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.exc import IntegrityError

from app.models.poll import Poll, PollOption, PollVote
from app.models.message import Message, MessageType
from app.models.conversation import ConversationMember
from app.models.user import User
from app.repositories.message_repo import MessageRepository


class PollService:
    """Service for poll operations with business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize poll service.

        Args:
            db: Database session
        """
        self.db = db

    async def _verify_conversation_membership(
        self,
        conversation_id: str,
        user_id: str
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

    async def create_poll(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        options: List[Dict[str, Any]],
        multiple_choice: bool = False,
        expires_at: Optional[datetime] = None
    ) -> "CreatePollResponse":
        """
        Create a new poll attached to a message.

        Args:
            user_id: Creator user UUID
            conversation_id: Conversation UUID
            question: Poll question
            options: List of option dicts with 'option_text' and 'position'
            multiple_choice: Allow multiple answers
            expires_at: Expiration datetime (None for no expiration)

        Returns:
            Created poll with message data

        Raises:
            HTTPException: If validation fails
        """
        # Verify user is conversation member
        if not await self._verify_conversation_membership(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Create message for poll using MessageRepository to auto-generate ID
        message_repo = MessageRepository(self.db)

        # Get next sequence number for deterministic ordering (Telegram/WhatsApp pattern)
        sequence_number = await message_repo.get_next_sequence_number(conversation_id)

        message = await message_repo.create(
            conversation_id=conversation_id,
            sender_id=user_id,
            content=question,  # Store question as message content
            type=MessageType.POLL,
            metadata_json={},
            sequence_number=sequence_number
        )
        await self.db.flush()  # Get message ID

        # Create poll with auto-generated ID
        poll = Poll(
            id=str(uuid.uuid4()),
            message_id=message.id,
            question=question,
            multiple_choice=multiple_choice,
            expires_at=expires_at
        )
        self.db.add(poll)
        await self.db.flush()  # Get poll ID

        # Create poll options with auto-generated IDs
        poll_options = []
        for opt_data in options:
            poll_option = PollOption(
                id=str(uuid.uuid4()),
                poll_id=poll.id,
                option_text=opt_data['option_text'],
                position=opt_data['position']
            )
            self.db.add(poll_option)
            poll_options.append(poll_option)

        await self.db.commit()

        # Refresh to get created_at timestamps
        await self.db.refresh(poll)
        await self.db.refresh(message)
        for opt in poll_options:
            await self.db.refresh(opt)

        # Import schemas
        from app.schemas.poll import CreatePollResponse
        from app.schemas.message import MessageResponse

        # Build MessageResponse model (not dict) for proper camelCase serialization
        message_response = MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            type=message.type,  # MessageType enum
            metadata_json={},
            reply_to_id=None,
            is_edited=False,
            created_at=message.created_at,
            updated_at=message.updated_at,
            deleted_at=None,
            status='sent',
            sequence_number=message.sequence_number
        )

        # Return Pydantic model (FastAPI auto-serializes with camelCase)
        return CreatePollResponse(
            poll=await self._build_poll_response(poll, user_id),
            message=message_response
        )

    async def vote_on_poll(
        self,
        poll_id: str,
        user_id: str,
        option_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Cast or update vote(s) on a poll with idempotent logic.

        Implements row-level locking and graceful constraint violation handling
        to prevent race conditions from concurrent vote requests.

        Args:
            poll_id: Poll UUID
            user_id: Voter user UUID
            option_ids: Option UUID(s) to vote for

        Returns:
            Updated poll data

        Raises:
            HTTPException: If validation fails
        """
        # Fetch poll with row-level lock to prevent concurrent modifications
        result = await self.db.execute(
            select(Poll).where(Poll.id == poll_id).with_for_update()
        )
        poll = result.scalar_one_or_none()

        if not poll:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        # Validate poll is open
        if poll.expires_at and poll.expires_at < utc_now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poll has expired"
            )

        # Verify user is conversation member
        result = await self.db.execute(
            select(Message).where(Message.id == poll.message_id)
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll message not found"
            )

        if not await self._verify_conversation_membership(message.conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation"
            )

        # Validate all option_ids belong to this poll
        result = await self.db.execute(
            select(PollOption).where(
                and_(
                    PollOption.poll_id == poll_id,
                    PollOption.id.in_(option_ids)
                )
            )
        )
        valid_options = result.scalars().all()

        if len(valid_options) != len(option_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid option ID(s)"
            )

        # Validate multiple choice constraint
        if not poll.multiple_choice and len(option_ids) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Single-choice poll allows only one option"
            )

        try:
            # IDEMPOTENT OPERATION: Delete all existing votes by this user
            # This prevents constraint violations and makes voting idempotent
            await self.db.execute(
                delete(PollVote).where(
                    and_(
                        PollVote.poll_id == poll_id,
                        PollVote.user_id == user_id
                    )
                )
            )

            # Flush deletes before inserts
            await self.db.flush()

            # Insert new votes
            for option_id in option_ids:
                vote = PollVote(
                    id=str(uuid.uuid4()),
                    poll_id=poll_id,
                    option_id=option_id,
                    user_id=user_id
                )
                self.db.add(vote)

            # Flush inserts
            await self.db.flush()

            # Commit transaction
            await self.db.commit()

        except IntegrityError as e:
            # Handle race condition gracefully - just return current state
            await self.db.rollback()
            logger.warning(f"Race condition detected in vote_on_poll for poll {poll_id}: {e}")

            # Refetch poll and return current state
            result = await self.db.execute(
                select(Poll).where(Poll.id == poll_id)
            )
            poll = result.scalar_one()
            return await self._build_poll_response(poll, user_id)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to vote on poll {poll_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to vote on poll: {str(e)}"
            )

        # Refresh poll to get updated vote counts
        await self.db.refresh(poll)

        # Return updated poll data
        return await self._build_poll_response(poll, user_id)

    async def close_poll(
        self,
        poll_id: str,
        user_id: str
    ) -> "PollResponse":
        """
        Close a poll (only creator can close).

        Args:
            poll_id: Poll UUID
            user_id: User UUID (must be poll creator)

        Returns:
            Closed poll data

        Raises:
            HTTPException: If not creator or poll not found
        """
        # Get poll with message
        result = await self.db.execute(
            select(Poll).where(Poll.id == poll_id)
        )
        poll = result.scalar_one_or_none()

        if not poll:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        # Get message to verify creator
        result = await self.db.execute(
            select(Message).where(Message.id == poll.message_id)
        )
        message = result.scalar_one_or_none()

        if not message or message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the poll creator can close the poll"
            )

        # Close poll by setting expires_at to now
        # Note: expires_at column is TIMESTAMP WITHOUT TIME ZONE, so strip timezone
        poll.expires_at = utc_now().replace(tzinfo=None)
        await self.db.commit()

        return await self._build_poll_response(poll, user_id)

    async def get_poll(
        self,
        poll_id: str,
        user_id: str
    ) -> "PollResponse":
        """
        Get poll details with results.

        Args:
            poll_id: Poll UUID
            user_id: Requesting user UUID

        Returns:
            Poll data with results

        Raises:
            HTTPException: If not found or no access
        """
        result = await self.db.execute(
            select(Poll).where(Poll.id == poll_id)
        )
        poll = result.scalar_one_or_none()

        if not poll:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        # Verify user has access (is member of conversation)
        result = await self.db.execute(
            select(Message).where(Message.id == poll.message_id)
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll message not found"
            )

        if not await self._verify_conversation_membership(message.conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this poll"
            )

        return await self._build_poll_response(poll, user_id)

    async def _build_poll_response(
        self,
        poll: Poll,
        user_id: str
    ) -> "PollResponse":
        """
        Build poll response with vote counts and user votes.
        Uses Pydantic schema for proper camelCase serialization.

        Args:
            poll: Poll instance
            user_id: Current user UUID

        Returns:
            PollResponse: Pydantic model (convert with .model_dump() if embedding in dicts)
        """
        from app.schemas.poll import PollResponse, PollOptionResponse

        # Get all options for this poll
        result = await self.db.execute(
            select(PollOption)
            .where(PollOption.poll_id == poll.id)
            .order_by(PollOption.position)
        )
        options = result.scalars().all()

        # Get all votes for this poll
        result = await self.db.execute(
            select(PollVote).where(PollVote.poll_id == poll.id)
        )
        votes = result.scalars().all()

        # Build option responses with vote counts
        option_responses = []
        total_votes = 0
        user_votes = []

        for option in options:
            # Get votes for this option
            option_votes = [v for v in votes if v.option_id == option.id]
            vote_count = len(option_votes)
            total_votes += vote_count

            # Check if current user voted for this option
            user_voted = any(v.user_id == user_id for v in option_votes)
            if user_voted:
                user_votes.append(option.id)

            # Get voter IDs (for anonymous=False polls, though we default to anonymous)
            voters = [v.user_id for v in option_votes]

            # Use Pydantic schema for proper serialization
            option_response = PollOptionResponse(
                id=option.id,
                poll_id=option.poll_id,
                option_text=option.option_text,
                position=option.position,
                vote_count=vote_count,
                voters=voters
            )
            option_responses.append(option_response)

        # Check if poll is closed
        is_closed = poll.expires_at is not None and poll.expires_at < utc_now()

        # Use Pydantic schema for proper camelCase serialization
        poll_response = PollResponse(
            id=poll.id,
            message_id=poll.message_id,
            question=poll.question,
            multiple_choice=poll.multiple_choice,
            is_closed=is_closed,
            expires_at=poll.expires_at,
            created_at=poll.created_at,
            options=option_responses,
            total_votes=total_votes,
            user_votes=user_votes
        )

        # Return Pydantic model (FastAPI will serialize with camelCase aliases)
        return poll_response
