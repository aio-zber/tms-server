"""
UserDeletedMessage model - tracks per-user message deletions.

Implements Messenger-style "Delete for Me" functionality where messages
can be hidden for individual users without affecting other users' view.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message


class UserDeletedMessage(Base):
    """
    Tracks messages that have been deleted "for me" by individual users.

    This enables Messenger-style deletion where:
    - "Delete for Me" adds an entry here (message hidden only for this user)
    - "Delete for Everyone" uses Message.deleted_at (message hidden for all)
    - "Clear Conversation" adds entries here for all messages (per-user)

    When fetching messages, exclude any messages in this table for the requesting user.
    """

    __tablename__ = "user_deleted_messages"

    # Composite primary key
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User who deleted the message for themselves"
    )

    message_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Message that was deleted for this user"
    )

    # Timestamp
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the user deleted this message"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="deleted_messages")
    message: Mapped["Message"] = relationship(back_populates="deleted_by_users")

    def __repr__(self) -> str:
        return f"<UserDeletedMessage(user_id={self.user_id}, message_id={self.message_id})>"


# Indexes for performance
Index("idx_user_deleted_messages_user", UserDeletedMessage.user_id)
Index("idx_user_deleted_messages_message", UserDeletedMessage.message_id)
