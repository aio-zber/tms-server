"""
Conversation and ConversationMember models.

Handles both direct messages (DM) and group chats.
"""
import enum
from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message
    from app.models.call import Call
    from app.models.muted_conversation import MutedConversation


class ConversationType(str, enum.Enum):
    """Enum for conversation types."""
    DM = "dm"
    GROUP = "group"


class ConversationRole(str, enum.Enum):
    """Enum for conversation member roles."""
    ADMIN = "admin"
    MEMBER = "member"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """
    Conversation model for DMs and group chats.

    A conversation can be:
    - DM: Direct message between two users
    - Group: Group chat with multiple users
    """

    __tablename__ = "conversations"

    # Conversation type
    type: Mapped[ConversationType] = mapped_column(
        SQLEnum(ConversationType, name="conversation_type", native_enum=False),
        nullable=False,
        doc="Type of conversation: 'dm' or 'group'"
    )

    # Group metadata (null for DMs)
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Group name (null for DMs)"
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Group avatar URL (null for DMs)"
    )

    # Creator reference
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who created the conversation"
    )

    # Relationships
    members: Mapped[List["ConversationMember"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin"  # Efficient bulk loading of members
    )

    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="select"  # Standard lazy loading for potentially large collections
    )

    calls: Mapped[List["Call"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="select"  # Standard lazy loading
    )

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])

    muted_by_users: Mapped[List["MutedConversation"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        doc="Users who have muted this conversation"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, type={self.type}, name={self.name})>"


class ConversationMember(Base):
    """
    ConversationMember model - association table for users in conversations.

    Tracks membership, roles, read status, and mute preferences.
    """

    __tablename__ = "conversation_members"

    # Composite primary key
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Conversation ID"
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User ID"
    )

    # Member role
    role: Mapped[ConversationRole] = mapped_column(
        SQLEnum(ConversationRole, name="conversation_role", native_enum=False),
        default=ConversationRole.MEMBER,
        nullable=False,
        doc="Member role: 'admin' or 'member'"
    )

    # Membership tracking
    joined_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the user joined the conversation"
    )

    last_read_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="Last time the user read messages in this conversation"
    )

    # Mute settings
    is_muted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        doc="Whether the conversation is muted for this user"
    )

    mute_until: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="Temporary mute expiration time (null for permanent mute)"
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="conversation_memberships")

    def __repr__(self) -> str:
        return (
            f"<ConversationMember(conversation_id={self.conversation_id}, "
            f"user_id={self.user_id}, role={self.role})>"
        )


# Indexes for performance
Index("idx_conversation_members_user", ConversationMember.user_id)
Index("idx_conversation_members_conversation", ConversationMember.conversation_id)
Index("idx_conversations_created_by", Conversation.created_by)
Index("idx_conversations_type", Conversation.type)
