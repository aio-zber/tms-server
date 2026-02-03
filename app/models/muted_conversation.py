"""
Muted Conversation Model

Tracks which conversations have been muted by which users.
Per-user muting allows different users to have different mute preferences.
"""
from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation


class MutedConversation(Base, UUIDMixin):
    """
    Muted conversation model.

    Represents a user's decision to mute a specific conversation.
    When a conversation is muted for a user, they won't receive
    notifications for that conversation (except @mentions).

    Relationships:
    - user: Many-to-one relationship with User
    - conversation: Many-to-one relationship with Conversation
    """

    __tablename__ = "muted_conversations"

    # Foreign keys
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the user who muted the conversation"
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the conversation that was muted"
    )

    # Timestamp
    muted_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the conversation was muted"
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="muted_conversations",
        doc="The user who muted this conversation"
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="muted_by_users",
        doc="The conversation that was muted"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'user_id',
            'conversation_id',
            name='uq_muted_conversations_user_conversation'
        ),
        Index('ix_muted_conversations_user_id', 'user_id'),
        Index('ix_muted_conversations_conversation_id', 'conversation_id'),
    )

    def __repr__(self) -> str:
        """String representation of MutedConversation."""
        return f"<MutedConversation(user_id={self.user_id}, conversation_id={self.conversation_id})>"
