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
from app.services.user_service import UserService


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

        # Use UserService to get current user (fetches from TMS and syncs to DB)
        try:
            user_service = UserService(db)
            user_response = await user_service.get_current_user(token)
            
            # Convert UserResponse to dict for backward compatibility
            user_dict = {
                "id": user_response.tms_user_id,  # Use TMS ID as primary identifier
                "tms_user_id": user_response.tms_user_id,
                "local_user_id": user_response.id,  # Local database ID
                "email": user_response.email,
                "username": user_response.username,
                "first_name": user_response.first_name,
                "last_name": user_response.last_name,
                "name": user_response.display_name,
                "display_name": user_response.display_name,
                "image": user_response.image,
                "role": user_response.role,
                "position_title": user_response.position_title,
                "division": user_response.division,
                "department": user_response.department,
                "section": user_response.section,
                "custom_team": user_response.custom_team,
                "is_active": user_response.is_active,
                "is_leader": user_response.is_leader,
                "settings": user_response.settings,
            }
            return user_dict
            
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
    user_role = current_user.get("role", "")

    # Check for ADMIN role (TMS uses uppercase)
    if user_role.upper() != "ADMIN":
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
