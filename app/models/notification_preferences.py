"""
Notification Preferences Model

Stores user-specific notification preferences including sound settings,
browser notifications, DND mode, and notification type toggles.
"""
from typing import TYPE_CHECKING
from datetime import time as Time

from sqlalchemy import ForeignKey, Boolean, Integer, Time as SQLTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class NotificationPreferences(Base, UUIDMixin, TimestampMixin):
    """
    User notification preferences model.

    Stores all notification-related settings for a user including:
    - Sound preferences (enabled, volume)
    - Browser notification preferences
    - Notification type preferences (messages, mentions, reactions, member activity)
    - Do Not Disturb (DND) schedule

    Relationships:
    - user: One-to-one relationship with User
    """

    __tablename__ = "notification_preferences"

    # Foreign key to users table
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        doc="Reference to the user who owns these preferences"
    )

    # Sound settings
    sound_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether notification sounds are enabled"
    )

    sound_volume: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=75,
        server_default="75",
        doc="Volume level for notification sounds (0-100)"
    )

    # Browser notifications
    browser_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether browser push notifications are enabled"
    )

    # Notification types
    enable_message_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Enable notifications for new messages"
    )

    enable_mention_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Enable notifications when mentioned (@username)"
    )

    enable_reaction_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Enable notifications for message reactions"
    )

    enable_member_activity_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Enable notifications for member join/leave events"
    )

    # Do Not Disturb mode
    dnd_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether Do Not Disturb mode is enabled"
    )

    dnd_start: Mapped[Time | None] = mapped_column(
        SQLTime,
        nullable=True,
        doc="DND start time (24-hour format, e.g., 22:00)"
    )

    dnd_end: Mapped[Time | None] = mapped_column(
        SQLTime,
        nullable=True,
        doc="DND end time (24-hour format, e.g., 08:00)"
    )

    # Relationship to User (one-to-one)
    user: Mapped["User"] = relationship(
        "User",
        back_populates="notification_preferences",
        doc="The user who owns these notification preferences"
    )

    def __repr__(self) -> str:
        """String representation of NotificationPreferences."""
        return f"<NotificationPreferences(user_id={self.user_id}, sound={self.sound_enabled}, dnd={self.dnd_enabled})>"
