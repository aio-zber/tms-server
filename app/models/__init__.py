"""
SQLAlchemy models for the TMS Messaging application.

All models must be imported here for Alembic auto-generation to work.
"""

# Import Base first
from app.models.base import Base, TimestampMixin, UUIDMixin

# Import all models (order matters for relationships)
from app.models.user import User
from app.models.conversation import Conversation, ConversationMember, ConversationType, ConversationRole
from app.models.message import Message, MessageStatus, MessageReaction, MessageType, MessageStatusType
from app.models.user_block import UserBlock
from app.models.call import Call, CallParticipant, CallType, CallStatus
from app.models.poll import Poll, PollOption, PollVote

# Export all models and enums
__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    # User
    "User",
    # Conversations
    "Conversation",
    "ConversationMember",
    "ConversationType",
    "ConversationRole",
    # Messages
    "Message",
    "MessageStatus",
    "MessageReaction",
    "MessageType",
    "MessageStatusType",
    # User blocking
    "UserBlock",
    # Calls
    "Call",
    "CallParticipant",
    "CallType",
    "CallStatus",
    # Polls
    "Poll",
    "PollOption",
    "PollVote",
]
