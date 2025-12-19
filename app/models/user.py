"""
User model - Local reference to TMS users.

This model stores minimal user data locally and syncs from TMS.
All authentication and user identity management is handled by TMS.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Index, String, JSON, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import ConversationMember
    from app.models.message import Message, MessageStatus, MessageReaction
    from app.models.user_block import UserBlock
    from app.models.call import CallParticipant
    from app.models.notification_preferences import NotificationPreferences
    from app.models.muted_conversation import MutedConversation


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

    # Basic user information (synced from TMS)
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="User email address from TMS"
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Username from TMS"
    )

    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="First name from TMS"
    )

    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Last name from TMS"
    )

    middle_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Middle name from TMS"
    )

    image: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Profile image URL from TMS"
    )

    contact_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Contact number from TMS"
    )

    # Role and organizational information
    role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="User role from TMS (ADMIN, LEADER, MEMBER)"
    )

    position_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Position title from TMS"
    )

    division: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Division from TMS"
    )

    department: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Department from TMS"
    )

    section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Section from TMS"
    )

    custom_team: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Custom team from TMS"
    )

    # Hierarchy and reporting
    hierarchy_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Hierarchy level from TMS"
    )

    reports_to_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="ID of reporting manager from TMS"
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Whether user is active in TMS"
    )

    is_leader: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether user is a leader in TMS"
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
        DateTime(timezone=True),
        nullable=True,
        doc="Last time user data was synced from TMS"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the user was first created locally"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="When the user was last updated"
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

    # Notification relationships
    notification_preferences: Mapped["NotificationPreferences | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        doc="User's notification preferences (one-to-one)"
    )

    muted_conversations: Mapped[List["MutedConversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        doc="Conversations muted by this user"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tms_user_id={self.tms_user_id})>"


# Note: tms_user_id already has a unique index from the column definition (unique=True, index=True)
# No need for additional manual index
