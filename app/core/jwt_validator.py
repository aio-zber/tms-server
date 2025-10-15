"""
JWT Token Validator for NextAuth tokens.
Validates JWT tokens locally without external API calls.
"""
import jwt
from typing import Dict, Any
from datetime import datetime
from app.config import settings


class JWTValidationError(Exception):
    """Raised when JWT validation fails."""
    pass


def decode_nextauth_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate NextAuth JWT token locally.

    This is MUCH faster than calling Team Management API for every request.

    Args:
        token: JWT token string (from Authorization: Bearer header)

    Returns:
        Decoded token payload with user info:
        {
            "user_id": "clxxxxx",      # User ID (from 'sub' claim)
            "email": "user@example.com",
            "name": "John Doe",
            "exp": 1234567890,          # Expiration timestamp
            "iat": 1234567890,          # Issued at timestamp
        }

    Raises:
        JWTValidationError: If token is invalid or expired

    Example:
        ```python
        try:
            payload = decode_nextauth_jwt(token)
            user_id = payload["user_id"]
        except JWTValidationError as e:
            raise HTTPException(401, detail=str(e))
        ```
    """
    try:
        # Decode JWT using NextAuth secret
        # NextAuth typically uses HS256 or HS512 algorithm
        payload = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=["HS256", "HS512", "RS256"],  # Support common algorithms
            options={
                "verify_exp": True,  # Verify expiration
                "verify_signature": True,  # Verify signature
            }
        )

        # Extract user information from JWT claims
        # Try "sub" first (standard JWT claim), then "id" (NextAuth custom claim)
        user_id = payload.get("sub") or payload.get("id")
        if not user_id:
            # Debug: Log the available claims to understand token structure
            available_claims = list(payload.keys())
            raise JWTValidationError(
                f"Token missing user ID claim ('sub' or 'id'). Available claims: {available_claims}"
            )

        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "picture": payload.get("picture"),  # Profile image
            "image": payload.get("image"),      # Alternative image field
            "role": payload.get("role"),
            "hierarchyLevel": payload.get("hierarchyLevel"),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
            # Include all other claims for flexibility
            **payload
        }

    except jwt.ExpiredSignatureError:
        raise JWTValidationError("Token has expired - please login again")

    except jwt.InvalidSignatureError:
        raise JWTValidationError("Invalid token signature - token may have been tampered with")

    except jwt.DecodeError as e:
        raise JWTValidationError(f"Failed to decode token: {str(e)}")

    except jwt.InvalidTokenError as e:
        raise JWTValidationError(f"Invalid token: {str(e)}")

    except Exception as e:
        raise JWTValidationError(f"Token validation failed: {str(e)}")


def extract_user_id_from_token(token: str) -> str:
    """
    Quick extraction of user ID from token without full validation.
    Use for cache key generation.

    Args:
        token: JWT token string

    Returns:
        User ID string

    Raises:
        JWTValidationError: If token cannot be decoded

    Example:
        ```python
        user_id = extract_user_id_from_token(token)
        cache_key = f"user:{user_id}"
        ```
    """
    payload = decode_nextauth_jwt(token)
    return payload["user_id"]


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without raising an exception.

    Args:
        token: JWT token string

    Returns:
        True if expired, False if still valid

    Example:
        ```python
        if is_token_expired(token):
            # Redirect to login
        ```
    """
    try:
        decode_nextauth_jwt(token)
        return False
    except JWTValidationError as e:
        if "expired" in str(e).lower():
            return True
        return False
