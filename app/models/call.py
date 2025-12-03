"""
Call and CallParticipant models.

Tracks voice and video calls, including participants and call history.
"""
import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Index, String, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation


class CallType(str, enum.Enum):
    """Enum for call types."""
    VOICE = "voice"
    VIDEO = "video"


class CallStatus(str, enum.Enum):
    """Enum for call completion statuses."""
    COMPLETED = "completed"
    MISSED = "missed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class Call(Base, UUIDMixin):
    """
    Call model - tracks voice and video calls.

    Stores call metadata and final status. Active signaling happens via WebRTC.
    """

    __tablename__ = "calls"

    # References
    conversation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Conversation where the call took place"
    )

    created_by: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who initiated the call"
    )

    # Call details
    type: Mapped[CallType] = mapped_column(
        SQLEnum(CallType, name="call_type", native_enum=False),
        nullable=False,
        doc="Type of call: voice or video"
    )

    status: Mapped[CallStatus] = mapped_column(
        SQLEnum(CallStatus, name="call_status", native_enum=False),
        nullable=False,
        doc="Final call status: completed, missed, declined, or cancelled"
    )

    # Call timing
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="When the call actually started (null if never answered)"
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="When the call ended"
    )

    # Creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the call was initiated"
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="calls")
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])

    participants: Mapped[List["CallParticipant"]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Call(id={self.id}, type={self.type}, status={self.status})>"


class CallParticipant(Base):
    """
    CallParticipant model - tracks who participated in a call.

    Records when each participant joined and left the call.
    """

    __tablename__ = "call_participants"

    # Composite primary key
    call_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("calls.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Call ID"
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User ID"
    )

    # Participation tracking
    joined_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="When the participant joined the call (null if never joined)"
    )

    left_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="When the participant left the call"
    )

    # Relationships
    call: Mapped["Call"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="call_participations")

    def __repr__(self) -> str:
        return f"<CallParticipant(call_id={self.call_id}, user_id={self.user_id})>"


# Indexes for performance
# Useful for querying calls by time
Index("idx_calls_created_at", Call.created_at)
# Composite PK columns for CallParticipant need indexes for queries
Index("idx_call_participants_call", CallParticipant.call_id)
Index("idx_call_participants_user", CallParticipant.user_id)
# Note: Call.conversation_id and Call.created_by already have index=True
