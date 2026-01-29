"""
User API endpoints.
Provides user management, search, and synchronization endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.services.user_service import UserService
from app.core.tms_client import TMSAPIException
from app.schemas.user import (
    UserResponse,
    UserSearchRequest,
    UserSyncRequest,
    UserSyncResponse
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(
    authorization: str = Header(..., description="Bearer token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user profile.

    This endpoint:
    1. Decodes NextAuth JWT token to get TMS user ID
    2. Fetches user from local database
    3. Returns user profile with local settings

    **Authentication**: Required (NextAuth JWT token in Authorization header)

    **Returns**: Full user profile with local settings
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ")[1]

    try:
        # Decode NextAuth token to get TMS user ID
        from app.core.security import decode_nextauth_token
        token_payload = decode_nextauth_token(token)
        tms_user_id = token_payload.get("id")

        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload - missing user ID"
            )

        # Get user from local database
        user_service = UserService(db)
        user = await user_service.get_user_by_tms_id(tms_user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )

        return user

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user by ID (local user ID or TMS user ID).

    Tries to find user by:
    1. Local UUID
    2. TMS user ID (if not found by UUID)

    **Authentication**: Required

    **Parameters**:
    - `user_id`: Local user UUID or TMS user ID

    **Returns**: User profile (public information)

    **Errors**:
    - 404: User not found
    """
    user_service = UserService(db)

    # Try local UUID first
    try:
        # UUID import removed - using str for ID types
        user = await user_service.get_user_by_id(user_id)
        if user:
            return user
    except ValueError:
        # Not a valid UUID, try as TMS user ID
        pass

    # Try TMS user ID
    user = await user_service.get_user_by_tms_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return user


@router.get("/", response_model=list[UserResponse])
async def search_users(
    q: str = Query("", min_length=0, max_length=100, description="Search query (empty returns all users)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    division: Optional[str] = Query(None, description="Filter by division"),
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search users by name, email, or username.

    **Search Strategy**:
    1. Searches local database first
    2. Falls back to TMS API if insufficient results
    3. Syncs TMS results to local DB
    4. Returns combined results
    5. If query is empty, returns all active users

    **Authentication**: Required

    **Query Parameters**:
    - `q`: Search query (0-100 characters, empty returns all users)
    - `limit`: Maximum results (1-100, default: 20)
    - `division`: Filter by division
    - `department`: Filter by department
    - `role`: Filter by role (ADMIN, LEADER, MEMBER)
    - `is_active`: Filter by active status

    **Returns**: List of matching users

    **Examples**:
    ```
    GET /api/v1/users?q=john&division=Engineering&limit=10
    GET /api/v1/users?q=&limit=50  # Get all users
    ```
    """
    # Build filters
    filters = {}
    if division:
        filters["division"] = division
    if department:
        filters["department"] = department
    if role:
        filters["role"] = role
    if is_active is not None:
        filters["is_active"] = is_active

    try:
        user_service = UserService(db)
        users = await user_service.search_users(
            query=q,
            filters=filters if filters else None,
            limit=limit
        )
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/sync", response_model=UserSyncResponse)
async def sync_users(
    sync_request: UserSyncRequest,
    admin_user: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger user synchronization from TMS.

    **Admin Only**: This endpoint requires admin privileges.

    **Request Body**:
    - `tms_user_ids`: Optional list of TMS user IDs to sync. If None, syncs active users.
    - `force`: Force sync even if recently synced (default: false)

    **Returns**: Sync statistics (synced_count, failed_count, errors)

    **Use Cases**:
    - Force refresh of specific users
    - Bulk sync after TMS updates
    - Troubleshooting sync issues

    **Example**:
    ```json
    {
      "tms_user_ids": ["tms-123", "tms-456"],
      "force": true
    }
    ```
    """
    try:
        user_service = UserService(db)

        if sync_request.tms_user_ids:
            # Sync specific users
            result = await user_service.sync_users_batch(
                tms_user_ids=sync_request.tms_user_ids,
                force=sync_request.force
            )
        else:
            # Sync active users needing refresh
            result = await user_service.sync_active_users(
                hours_threshold=12 if not sync_request.force else 0,
                batch_size=100
            )

        return UserSyncResponse(
            success=result.get("failed", result.get("failed_count", 0)) == 0,
            synced_count=result.get("synced", result.get("success_count", 0)),
            failed_count=result.get("failed", result.get("failed_count", 0)),
            errors=result.get("errors", [])
        )

    except TMSAPIException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"TMS API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.delete("/cache/{tms_user_id}")
async def invalidate_user_cache(
    tms_user_id: str,
    admin_user: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invalidate cached user data.

    **Admin Only**: This endpoint requires admin privileges.

    **Parameters**:
    - `tms_user_id`: TMS user ID to invalidate cache for

    **Returns**: Success status

    **Use Case**: Force cache refresh after TMS data changes
    """
    try:
        user_service = UserService(db)
        success = await user_service.invalidate_user_cache(tms_user_id)

        if success:
            return {"success": True, "message": f"Cache invalidated for user {tms_user_id}"}
        else:
            return {"success": False, "message": "Cache not found or already expired"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.get("/presence/online", response_model=list[str])
async def get_online_users(
    current_user: dict = Depends(get_current_user),
):
    """
    Get list of currently online user IDs.

    Returns the user IDs (UUIDs) of all users who have active WebSocket connections.
    This is used to display online status indicators (green dots) in the UI.

    **Authentication**: Required

    **Returns**: List of online user IDs (local UUIDs)

    **Messenger-style Behavior**:
    - User is online when they have at least one active WebSocket connection
    - User goes offline when all their connections are closed
    - Multiple device support: user stays online if ANY device is connected
    """
    from app.core.cache import get_online_user_ids

    # Return globally accurate online users from Redis (all workers)
    online_user_ids = await get_online_user_ids()
    return list(online_user_ids)
