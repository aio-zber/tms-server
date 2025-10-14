"""
Custom validators for application data.
Provides reusable validation functions.
"""
import re
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status


def validate_uuid(value: str, field_name: str = "ID") -> UUID:
    """
    Validate and convert string to UUID.

    Args:
        value: String value to validate
        field_name: Name of the field for error messages

    Returns:
        UUID object

    Raises:
        HTTPException: If value is not a valid UUID
    """
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: must be a valid UUID"
        )


def validate_emoji(emoji: str) -> bool:
    """
    Validate if string is a valid emoji.

    Args:
        emoji: String to validate

    Returns:
        True if valid emoji, False otherwise
    """
    # Basic emoji validation - checks for common emoji ranges
    # This is a simplified version; a more robust solution would use emoji library
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.match(emoji))


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text content to prevent XSS attacks.

    Args:
        text: Text to sanitize
        max_length: Optional maximum length

    Returns:
        Sanitized text
    """
    if not text:
        return text

    # Remove potentially dangerous HTML/script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)

    # Truncate if max_length specified
    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text.strip()


def validate_file_type(mime_type: str, allowed_types: list) -> bool:
    """
    Validate file MIME type.

    Args:
        mime_type: MIME type to validate
        allowed_types: List of allowed MIME types

    Returns:
        True if valid, False otherwise
    """
    return mime_type.lower() in [t.lower() for t in allowed_types]


def validate_file_size(size_bytes: int, max_size: int) -> bool:
    """
    Validate file size.

    Args:
        size_bytes: File size in bytes
        max_size: Maximum allowed size in bytes

    Returns:
        True if valid, False otherwise
    """
    return 0 < size_bytes <= max_size


def validate_conversation_name(name: str) -> bool:
    """
    Validate conversation/group name.

    Args:
        name: Conversation name

    Returns:
        True if valid, False otherwise
    """
    if not name or len(name.strip()) == 0:
        return False

    if len(name) > 255:
        return False

    # Check for invalid characters
    invalid_chars = ['<', '>', '{', '}', '[', ']', '\\', '|', '^', '`']
    if any(char in name for char in invalid_chars):
        return False

    return True


def validate_message_content(content: str, message_type: str) -> bool:
    """
    Validate message content based on type.

    Args:
        content: Message content
        message_type: Type of message

    Returns:
        True if valid, False otherwise
    """
    if message_type == "text":
        # Text messages must have content
        return bool(content and len(content.strip()) > 0)

    # Other message types may have empty content
    return True


def validate_pagination_params(limit: int, cursor: Optional[str] = None) -> dict:
    """
    Validate and normalize pagination parameters.

    Args:
        limit: Requested limit
        cursor: Optional cursor

    Returns:
        Validated pagination dict

    Raises:
        HTTPException: If parameters are invalid
    """
    # Validate limit
    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be at least 1"
        )

    if limit > 100:
        limit = 100  # Cap at maximum

    # Validate cursor if provided
    cursor_uuid = None
    if cursor:
        cursor_uuid = validate_uuid(cursor, "cursor")

    return {
        "limit": limit,
        "cursor": cursor_uuid
    }


def validate_search_query(query: str) -> str:
    """
    Validate and sanitize search query.

    Args:
        query: Search query string

    Returns:
        Sanitized query

    Raises:
        HTTPException: If query is invalid
    """
    if not query or len(query.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty"
        )

    if len(query) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query too long (max 200 characters)"
        )

    # Sanitize query
    query = sanitize_text(query)

    # Remove SQL wildcards to prevent injection
    query = query.replace('%', '').replace('_', '')

    return query.strip()
