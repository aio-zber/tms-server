"""
Centralized datetime utilities for TMS Server

Ensures consistent timezone handling across the application.
All timestamps are stored and transmitted as UTC with explicit timezone indicators.

References: Messenger and Telegram timestamp patterns
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    Use this instead of datetime.utcnow() to ensure timezone awareness.

    Returns:
        datetime: Current time in UTC with timezone info

    Example:
        >>> now = utc_now()
        >>> now.tzinfo  # timezone.utc
    """
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """
    Ensure datetime is UTC timezone-aware.

    Converts naive datetime (assumed to be UTC) to timezone-aware UTC.
    If datetime is already timezone-aware, converts to UTC.

    Args:
        dt: Datetime object (naive or aware) or None

    Returns:
        datetime | None: UTC timezone-aware datetime or None

    Example:
        >>> naive_dt = datetime(2025, 12, 16, 11, 30)  # Naive
        >>> aware_dt = ensure_utc(naive_dt)
        >>> aware_dt.tzinfo  # timezone.utc
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)

    # Already aware - convert to UTC
    return dt.astimezone(timezone.utc)


def to_iso_utc(dt: datetime | None) -> str | None:
    """
    Convert datetime to ISO format with 'Z' suffix (UTC indicator).

    This ensures the frontend correctly interprets timestamps as UTC.
    PostgreSQL TIMESTAMPTZ will serialize with '+00:00', which this
    function converts to 'Z' for consistency.

    Args:
        dt: Datetime object or None

    Returns:
        str | None: ISO 8601 string with 'Z' suffix (e.g., "2025-12-16T11:30:00.123456Z")
                   or None if input is None

    Example:
        >>> dt = datetime(2025, 12, 16, 11, 30, 0, 123456, tzinfo=timezone.utc)
        >>> to_iso_utc(dt)
        "2025-12-16T11:30:00.123456Z"
    """
    if dt is None:
        return None

    # Ensure UTC timezone-aware
    utc_dt = ensure_utc(dt)

    # Convert to ISO format and replace '+00:00' with 'Z'
    # PostgreSQL TIMESTAMPTZ outputs '+00:00', but 'Z' is more standard
    return utc_dt.isoformat().replace('+00:00', 'Z')
