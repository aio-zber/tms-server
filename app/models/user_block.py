"""
UserBlock model for user blocking functionality.

Allows users to block other users from sending them messages.
"""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserBlock(Base):
    """
    UserBlock model - tracks which users have blocked each other.

    When a user blocks another:
    - The blocked user cannot send messages to the blocker
    - The blocker won't receive messages from the blocked user
    - DM conversations between them become inactive
    """

    __tablename__ = "user_blocks"

    # Composite primary key
    blocker_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User who is blocking"
    )

    blocked_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User who is being blocked"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="When the block was created"
    )

    # Relationships
    blocker: Mapped["User"] = relationship(
        back_populates="blocked_users",
        foreign_keys=[blocker_id]
    )

    blocked: Mapped["User"] = relationship(
        back_populates="blocked_by_users",
        foreign_keys=[blocked_id]
    )

    def __repr__(self) -> str:
        return f"<UserBlock(blocker_id={self.blocker_id}, blocked_id={self.blocked_id})>"


# Indexes for performance
Index("idx_user_blocks_blocker", UserBlock.blocker_id)
Index("idx_user_blocks_blocked", UserBlock.blocked_id)
