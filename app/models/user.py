"""
User model - Local reference to TMS users.

This model stores minimal user data locally and syncs from TMS.
All authentication and user identity management is handled by TMS.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Index, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import ConversationMember
    from app.models.message import Message, MessageStatus, MessageReaction
    from app.models.user_block import UserBlock
    from app.models.call import CallParticipant


class User(Base, UUIDMixin):
    """
    User model - Local reference to TMS users.

    Stores minimal user data locally. Full user data is fetched from TMS
    and cached in Redis. This model primarily tracks local settings and
    synchronization state.
    """

    __tablename__ = "users"

    # TMS reference (unique identifier from TMS)
    tms_user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique user ID from Team Management System"
    )

    # Local user settings (stored as JSONB)
    settings_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="User-specific settings (notifications, preferences, etc.)"
    )

    # Synchronization tracking
    last_synced_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="Last time user data was synced from TMS"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the user was first created locally"
    )

    # Relationships
    conversation_memberships: Mapped[List["ConversationMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    sent_messages: Mapped[List["Message"]] = relationship(
        back_populates="sender",
        foreign_keys="Message.sender_id"
    )

    message_statuses: Mapped[List["MessageStatus"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    message_reactions: Mapped[List["MessageReaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # User blocking relationships
    blocked_users: Mapped[List["UserBlock"]] = relationship(
        back_populates="blocker",
        foreign_keys="UserBlock.blocker_id",
        cascade="all, delete-orphan"
    )

    blocked_by_users: Mapped[List["UserBlock"]] = relationship(
        back_populates="blocked",
        foreign_keys="UserBlock.blocked_id",
        cascade="all, delete-orphan"
    )

    call_participations: Mapped[List["CallParticipant"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tms_user_id={self.tms_user_id})>"


# Note: tms_user_id already has a unique index from the column definition (unique=True, index=True)
# No need for additional manual index
