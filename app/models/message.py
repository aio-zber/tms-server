"""
Message, MessageStatus, and MessageReaction models.

Handles all message types, delivery status, and reactions.
"""
import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    JSON,
    UniqueConstraint,
    Enum as SQLEnum,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation
    from app.models.poll import Poll
    from app.models.user_deleted_message import UserDeletedMessage


class MessageType(str, enum.Enum):
    """Enum for message types."""
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"
    VOICE = "VOICE"
    POLL = "POLL"
    CALL = "CALL"
    SYSTEM = "SYSTEM"  # System-generated messages for conversation events


class MessageStatusType(str, enum.Enum):
    """Enum for message status types."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class Message(Base, UUIDMixin):
    """
    Message model for all message types.

    Supports text, images, files, voice messages, polls, and call notifications.
    """

    __tablename__ = "messages"

    # References
    conversation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Conversation this message belongs to"
    )

    sender_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who sent the message"
    )

    # Message content
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Message text content (null for non-text messages)"
    )

    type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType, name="message_type", native_enum=False),
        nullable=False,
        doc="Type of message: text, image, file, voice, poll, or call"
    )

    # Flexible metadata for different message types
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Flexible metadata (file URLs, image dimensions, voice duration, etc.)"
    )

    # Threading
    reply_to_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="ID of message this is replying to"
    )

    # Message state
    is_edited: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        doc="Whether the message has been edited"
    )

    # Sequence number for deterministic ordering
    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Monotonically increasing sequence number per conversation (ensures stable ordering)"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="When the message was created"
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the message was last updated"
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Soft delete timestamp"
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(
        back_populates="sent_messages",
        foreign_keys=[sender_id]
    )

    # Self-referential relationship for replies
    reply_to: Mapped["Message | None"] = relationship(
        remote_side="Message.id",  # Use string reference to avoid circular dependency
        foreign_keys=[reply_to_id]
    )

    # Message status and reactions
    statuses: Mapped[List["MessageStatus"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin"  # Efficient loading of statuses with messages
    )

    reactions: Mapped[List["MessageReaction"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin"  # Efficient loading of reactions with messages
    )

    # Poll relationship (one-to-one)
    poll: Mapped["Poll | None"] = relationship(
        back_populates="message",
        uselist=False
    )

    # Per-user deletions (Messenger-style "Delete for Me")
    deleted_by_users: Mapped[List["UserDeletedMessage"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] if self.content else f"<{self.type}>"
        return f"<Message(id={self.id}, type={self.type}, content='{content_preview}...')>"


class MessageStatus(Base):
    """
    MessageStatus model - tracks delivery and read receipts.

    Each user in a conversation has their own status for each message.
    """

    __tablename__ = "message_status"

    # Composite primary key
    message_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Message ID"
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User ID"
    )

    # Status
    status: Mapped[MessageStatusType] = mapped_column(
        SQLEnum(MessageStatusType, name="message_status_type", native_enum=False),
        nullable=False,
        doc="Status: sent, delivered, or read"
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the status was recorded"
    )

    # Relationships
    message: Mapped["Message"] = relationship(back_populates="statuses")
    user: Mapped["User"] = relationship(back_populates="message_statuses")

    def __repr__(self) -> str:
        return (
            f"<MessageStatus(message_id={self.message_id}, "
            f"user_id={self.user_id}, status={self.status})>"
        )


class MessageReaction(Base, UUIDMixin):
    """
    MessageReaction model - emoji reactions to messages.

    Each user can react with multiple different emojis to the same message.
    """

    __tablename__ = "message_reactions"

    # References
    message_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Message ID"
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User ID"
    )

    # Reaction emoji
    emoji: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Emoji reaction (e.g., '👍', '❤️', '😂')"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the reaction was added"
    )

    # Relationships
    message: Mapped["Message"] = relationship(back_populates="reactions")
    user: Mapped["User"] = relationship(back_populates="message_reactions")

    # Unique constraint: one user can't use the same emoji twice on the same message
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_user_emoji"),
    )

    def __repr__(self) -> str:
        return f"<MessageReaction(message_id={self.message_id}, user_id={self.user_id}, emoji={self.emoji})>"


# Indexes for performance
# Composite index for message queries sorted by sequence number (primary) and time (fallback)
Index("idx_messages_conversation_seq",
      Message.conversation_id,
      Message.sequence_number.desc(),
      Message.created_at.desc())

# Unique constraint on (conversation_id, sequence_number) to ensure no duplicate sequences
UniqueConstraint(Message.conversation_id, Message.sequence_number, name="uq_conversation_sequence")

# Composite index for message status queries
Index("idx_message_status_user", MessageStatus.user_id, MessageStatus.status)
# Note: Single-column indexes removed - already created by index=True on columns
