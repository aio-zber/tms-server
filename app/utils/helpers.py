"""
Helper functions for common operations.
Provides reusable utility functions.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
# UUID import removed - using str for ID types
import hashlib
import json


def generate_cache_key(*parts: str) -> str:
    """
    Generate a cache key from parts.

    Args:
        *parts: Parts to combine into cache key

    Returns:
        Cache key string

    Example:
        >>> generate_cache_key("user", "123", "profile")
        'user:123:profile'
    """
    return ":".join(str(part) for part in parts)


def calculate_hash(data: str) -> str:
    """
    Calculate SHA256 hash of data.

    Args:
        data: Data to hash

    Returns:
        Hex digest of hash

    Example:
        >>> calculate_hash("hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    return hashlib.sha256(data.encode()).hexdigest()


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialize datetime to ISO format string.

    Args:
        dt: Datetime object

    Returns:
        ISO format string or None

    Example:
        >>> serialize_datetime(datetime(2025, 10, 10, 12, 0))
        '2025-10-10T12:00:00'
    """
    return dt.isoformat() if dt else None


def deserialize_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """
    Deserialize ISO format string to datetime.

    Args:
        dt_str: ISO format datetime string

    Returns:
        Datetime object or None

    Example:
        >>> deserialize_datetime('2025-10-10T12:00:00')
        datetime(2025, 10, 10, 12, 0)
    """
    return datetime.fromisoformat(dt_str) if dt_str else None


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")

    Example:
        >>> format_file_size(1572864)
        '1.50 MB'
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text

    Example:
        >>> truncate_text("This is a long text", 10)
        'This is...'
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def build_response(
    success: bool,
    data: Any = None,
    error: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build standard API response.

    Args:
        success: Success status
        data: Response data
        error: Error details
        message: Optional message

    Returns:
        Standardized response dict

    Example:
        >>> build_response(True, {"id": "123"})
        {'success': True, 'data': {'id': '123'}, 'error': None}
    """
    response = {
        "success": success,
        "data": data,
        "error": error
    }

    if message:
        response["message"] = message

    return response


def build_pagination_response(
    data: List[Any],
    next_cursor: Optional[str] = None,
    has_more: bool = False,
    total: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build paginated response.

    Args:
        data: List of items
        next_cursor: Cursor for next page
        has_more: Whether more items exist
        total: Optional total count

    Returns:
        Paginated response dict

    Example:
        >>> build_pagination_response([1, 2, 3], has_more=True)
        {'data': [1, 2, 3], 'pagination': {'next_cursor': None, 'has_more': True}}
    """
    pagination = {
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": has_more
    }

    if total is not None:
        pagination["total"] = total

    return {
        "data": data,
        "pagination": pagination
    }


def extract_mention_user_ids(text: str) -> List[str]:
    """
    Extract user IDs from @mentions in text.

    Args:
        text: Text containing @mentions

    Returns:
        List of mentioned user IDs

    Example:
        >>> extract_mention_user_ids("Hello @user123 and @user456")
        ['user123', 'user456']
    """
    import re

    # Pattern to match @username or @user:id format
    pattern = r'@(\w+)'
    matches = re.findall(pattern, text)

    return matches


def build_notification_payload(
    notification_type: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build notification payload.

    Args:
        notification_type: Type of notification
        title: Notification title
        body: Notification body
        data: Additional data

    Returns:
        Notification payload dict
    """
    return {
        "type": notification_type,
        "title": title,
        "body": body,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    }


def merge_dicts(*dicts: Dict) -> Dict:
    """
    Merge multiple dictionaries.

    Args:
        *dicts: Dictionaries to merge

    Returns:
        Merged dictionary

    Example:
        >>> merge_dicts({"a": 1}, {"b": 2}, {"c": 3})
        {'a': 1, 'b': 2, 'c': 3}
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def is_within_time_range(
    target_time: datetime,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> bool:
    """
    Check if time is within range.

    Args:
        target_time: Time to check
        start_time: Optional start of range
        end_time: Optional end of range

    Returns:
        True if within range, False otherwise
    """
    if start_time and target_time < start_time:
        return False

    if end_time and target_time > end_time:
        return False

    return True


def calculate_time_ago(dt: datetime) -> str:
    """
    Calculate human-readable time ago string.

    Args:
        dt: Datetime to compare with now

    Returns:
        Time ago string (e.g., "2 hours ago")

    Example:
        >>> calculate_time_ago(datetime.utcnow() - timedelta(hours=2))
        '2 hours ago'
    """
    now = datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely load JSON with default fallback.

    Args:
        json_str: JSON string
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """
    Safely dump object to JSON with default fallback.

    Args:
        obj: Object to serialize
        default: Default value if serialization fails

    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return default
