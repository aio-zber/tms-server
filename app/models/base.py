"""
Base model classes and mixins for SQLAlchemy ORM.
Provides common functionality for all database models.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Includes AsyncAttrs mixin for async relationship access.
    All models should inherit from this class.
    """
    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the record was created"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        onupdate=func.now(),
        nullable=True,
        doc="Timestamp when the record was last updated"
    )


class UUIDMixin:
    """
    Mixin for string ID primary key.

    Note: Changed from UUID to String to support CUID format IDs from TMS.
    CUID format: 25 characters (e.g., 'cmgoip1nt0001s89pzkw7bzlg')
    UUID format: 36 characters (e.g., '550e8400-e29b-41d4-a716-446655440000')
    """

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        doc="String ID primary key (supports CUID and UUID formats)"
    )


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID v4."""
    return uuid.uuid4()
