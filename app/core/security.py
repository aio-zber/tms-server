"""
Security utilities for authentication and authorization.
Handles JWT token validation and TMS integration.
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.config import settings


class SecurityException(HTTPException):
    """Custom exception for security-related errors."""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.

    Args:
        data: Payload data to encode
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token

    Example:
        ```python
        token = create_access_token(
            data={"sub": user_id, "tms_user_id": "123"},
            expires_delta=timedelta(hours=24)
        )
        ```
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        SecurityException: If token is invalid or expired

    Example:
        ```python
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except SecurityException:
            # Handle invalid token
            pass
        ```
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise SecurityException("Token has expired")
    except jwt.InvalidTokenError:
        raise SecurityException("Invalid token")


def validate_tms_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token (DEPRECATED - DO NOT USE).

    IMPORTANT: This function is deprecated and should not be used for validating
    GCGC NextAuth tokens. Token validation happens via GCGC's /api/v1/users/me
    endpoint, not through local JWT decoding.

    The JWT secret in this service may not match GCGC's NEXTAUTH_SECRET,
    so local token decoding will fail. Always validate tokens by calling
    GCGC's API endpoints.

    Args:
        token: JWT token

    Returns:
        Token payload (NOT RELIABLE - use tms_client.get_current_user_from_tms instead)

    Raises:
        SecurityException: Always raises - this function should not be used

    Example (CORRECT):
        ```python
        # Don't use this function! Use the TMS client instead:
        from app.core.tms_client import tms_client
        user_info = await tms_client.get_current_user_from_tms(token)
        ```
    """
    raise SecurityException(
        "Local JWT validation is not supported. "
        "Use tms_client.get_current_user_from_tms() to validate tokens with GCGC."
    )


def extract_token_from_header(authorization: str) -> str:
    """
    Extract JWT token from Authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        Extracted token

    Raises:
        SecurityException: If header format is invalid

    Example:
        ```python
        token = extract_token_from_header("Bearer eyJhbG...")
        ```
    """
    if not authorization:
        raise SecurityException("Missing authorization header")

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise SecurityException("Invalid authorization header format")

    return parts[1]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hashed password.

    Note: This is a placeholder. In production with TMS integration,
    password verification happens on TMS side.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    # This would typically use passlib or bcrypt
    # But since we rely on TMS for auth, this is a placeholder
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """
    Hash password.

    Note: This is a placeholder. TMS handles password hashing.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)
