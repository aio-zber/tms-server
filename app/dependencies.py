"""
Dependency injection for FastAPI routes.
Provides reusable dependencies for authentication, database sessions, etc.
"""
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import extract_token_from_header, validate_tms_token, SecurityException
from app.core.tms_client import tms_client, TMSAPIException


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Dependency to get the current authenticated user.

    This function:
    1. Extracts the JWT token from the Authorization header
    2. Validates the token with TMS
    3. Fetches user data from TMS (with caching)
    4. Returns the user information

    Args:
        authorization: Authorization header containing Bearer token
        db: Database session

    Returns:
        Dictionary containing user information from TMS

    Raises:
        HTTPException: 401 if token is missing or invalid

    Example:
        ```python
        @app.get("/protected")
        async def protected_route(current_user: dict = Depends(get_current_user)):
            return {"user": current_user["username"]}
        ```
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Extract token from "Bearer <token>" format
        token = extract_token_from_header(authorization)

        # Validate token with TMS
        token_payload = validate_tms_token(token)
        tms_user_id = token_payload.get("tms_user_id")

        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user information",
            )

        # Fetch user data from TMS (cached)
        try:
            user_data = await tms_client.get_user(tms_user_id, use_cache=True)
            return user_data
        except TMSAPIException as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch user data: {str(e)}",
            )

    except SecurityException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    Dependency to optionally get the current authenticated user.

    Similar to get_current_user but returns None instead of raising
    an exception if no valid token is provided.

    Args:
        authorization: Authorization header containing Bearer token
        db: Database session

    Returns:
        User information dictionary or None if not authenticated

    Example:
        ```python
        @app.get("/public-or-private")
        async def flexible_route(user: Optional[dict] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user['username']}"}
            return {"message": "Hello anonymous"}
        ```
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None


async def get_admin_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to verify the current user is an admin.

    Args:
        current_user: Current authenticated user

    Returns:
        User information if user is admin

    Raises:
        HTTPException: 403 if user is not an admin

    Example:
        ```python
        @app.delete("/admin/users/{user_id}")
        async def delete_user(
            user_id: str,
            admin: dict = Depends(get_admin_user)
        ):
            # Only admins can access this
            pass
        ```
    """
    user_role = current_user.get("role", "").lower()

    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user


def get_pagination_params(
    cursor: Optional[str] = None,
    limit: int = 50
) -> dict:
    """
    Dependency for cursor-based pagination parameters.

    Args:
        cursor: Cursor for pagination (typically last item ID)
        limit: Number of items to return (default: 50, max: 100)

    Returns:
        Dictionary with pagination parameters

    Example:
        ```python
        @app.get("/messages")
        async def get_messages(
            pagination: dict = Depends(get_pagination_params)
        ):
            cursor = pagination["cursor"]
            limit = pagination["limit"]
            # Use cursor and limit to fetch paginated results
        ```
    """
    # Enforce maximum limit
    if limit > 100:
        limit = 100
    elif limit < 1:
        limit = 1

    return {
        "cursor": cursor,
        "limit": limit,
    }
