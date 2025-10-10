"""
Poll, PollOption, and PollVote models.

Handles polls within messages, including voting and results.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Poll(Base, UUIDMixin):
    """
    Poll model - polls attached to messages.

    A poll is always associated with a message. Users can vote on poll options.
    """

    __tablename__ = "polls"

    # Reference to message (one-to-one)
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        doc="Message this poll is attached to"
    )

    # Poll details
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Poll question"
    )

    multiple_choice: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        doc="Whether users can select multiple options"
    )

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="When the poll expires (null for no expiration)"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the poll was created"
    )

    # Relationships
    message: Mapped["Message"] = relationship(back_populates="poll")

    options: Mapped[List["PollOption"]] = relationship(
        back_populates="poll",
        cascade="all, delete-orphan",
        order_by="PollOption.position",
        lazy="selectin"  # Always load options with polls
    )

    votes: Mapped[List["PollVote"]] = relationship(
        back_populates="poll",
        cascade="all, delete-orphan",
        lazy="select"  # Lazy load votes (can be many)
    )

    def __repr__(self) -> str:
        return f"<Poll(id={self.id}, question='{self.question[:50]}...')>"


class PollOption(Base, UUIDMixin):
    """
    PollOption model - individual options in a poll.

    Each poll has multiple options that users can vote on.
    """

    __tablename__ = "poll_options"

    # Reference to poll
    poll_id: Mapped[UUID] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Poll this option belongs to"
    )

    # Option details
    option_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Text of the poll option"
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Display position/order of this option"
    )

    # Relationships
    poll: Mapped["Poll"] = relationship(back_populates="options")

    votes: Mapped[List["PollVote"]] = relationship(
        back_populates="option",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PollOption(id={self.id}, option_text='{self.option_text}')>"


class PollVote(Base, UUIDMixin):
    """
    PollVote model - user votes on poll options.

    Tracks which users voted for which options. For single-choice polls,
    each user can only vote once (enforced by unique constraint on poll_id + user_id).
    """

    __tablename__ = "poll_votes"

    # References
    poll_id: Mapped[UUID] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Poll ID"
    )

    option_id: Mapped[UUID] = mapped_column(
        ForeignKey("poll_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Poll option ID"
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who voted"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the vote was cast"
    )

    # Relationships
    poll: Mapped["Poll"] = relationship(back_populates="votes")
    option: Mapped["PollOption"] = relationship(back_populates="votes")
    voter: Mapped["User"] = relationship(foreign_keys=[user_id])

    # Unique constraint: one vote per user per option
    # (Note: For single-choice polls, app logic should prevent multiple votes)
    __table_args__ = (
        UniqueConstraint("poll_id", "option_id", "user_id", name="uq_poll_option_user"),
    )

    def __repr__(self) -> str:
        return f"<PollVote(poll_id={self.poll_id}, option_id={self.option_id}, user_id={self.user_id})>"


# Indexes for performance
# Poll.message_id already has unique index from unique=True
# Note: Single-column indexes removed - already created by index=True on columns
