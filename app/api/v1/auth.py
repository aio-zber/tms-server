"""
Authentication API endpoints.
Provides login functionality and token validation using TMS integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.core.database import get_db
from app.services.user_service import UserService
from app.core.tms_client import tms_client, TMSAPIException
from app.schemas.user import UserResponse

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema for proxy authentication."""
    token: str = Field(..., description="TMS JWT token to validate")


class LoginResponse(BaseModel):
    """Login response schema."""
    success: bool
    user: UserResponse
    message: str = "Login successful"


class TokenValidationResponse(BaseModel):
    """Token validation response schema."""
    valid: bool
    user: Optional[UserResponse] = None
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate TMS authentication and sync user data.

    Supports two authentication methods:
    1. **Session cookies** (NextAuth) - Preferred for frontend login
    2. **JWT Bearer tokens** - For API clients

    **Flow:**
    1. Extract cookies from request (for NextAuth session)
    2. Validate with TMS using cookies OR token
    3. Fetch user profile from TMS /users/me
    4. Sync user data to local database
    5. Return user profile

    **Request Body:**
    ```json
    {
        "token": "session-token-or-jwt"
    }
    ```

    **Returns:** User profile if authentication is valid

    **Errors:**
    - 401: Invalid or expired authentication
    - 503: TMS service unavailable
    """
    try:
        # Use UserService with cookies support
        user_service = UserService(db)

        # Forward request cookies to TMS for session-based auth
        cookies = dict(request.cookies)

        user = await user_service.get_current_user(
            token=login_request.token,
            cookies=cookies if cookies else None
        )

        return LoginResponse(
            success=True,
            user=user,
            message="Login successful"
        )
        
    except TMSAPIException as e:
        error_message = str(e)
        status_code = status.HTTP_401_UNAUTHORIZED
        
        # Determine appropriate status code based on error
        if "unavailable" in error_message.lower() or "request failed" in error_message.lower():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
            
        raise HTTPException(
            status_code=status_code,
            detail=error_message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate TMS token without syncing user data.
    
    Lightweight endpoint to check if a token is valid.
    Useful for client-side token validation.
    
    **Request Body:**
    ```json
    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    
    **Returns:**
    ```json
    {
        "valid": true,
        "user": { ... },
        "message": "Token is valid"
    }
    ```
    
    **Note:** This endpoint is faster than `/login` as it doesn't sync user data.
    """
    try:
        # Just fetch user from TMS without syncing to DB
        tms_user_data = await tms_client.get_current_user_from_tms(request.token, use_cache=True)
        
        # Create minimal user response
        user_response = UserResponse(
            id="temp",  # Temporary ID since we're not syncing
            tms_user_id=tms_user_data["id"],
            email=tms_user_data.get("email", ""),
            username=tms_user_data.get("username", ""),
            first_name=tms_user_data.get("firstName", ""),
            last_name=tms_user_data.get("lastName", ""),
            middle_name=tms_user_data.get("middleName"),
            name=tms_user_data.get("name"),
            display_name=tms_user_data.get("name") or f"{tms_user_data.get('firstName', '')} {tms_user_data.get('lastName', '')}".strip(),
            image=tms_user_data.get("image"),
            role=tms_user_data.get("role", "MEMBER"),
            position_title=tms_user_data.get("positionTitle"),
            division=tms_user_data.get("division"),
            department=tms_user_data.get("department"),
            section=tms_user_data.get("section"),
            custom_team=tms_user_data.get("customTeam"),
            is_active=tms_user_data.get("isActive", True),
            is_leader=tms_user_data.get("isLeader", False),
            last_synced_at=None,
            created_at=None,
            settings=None,
        )
        
        return TokenValidationResponse(
            valid=True,
            user=user_response,
            message="Token is valid"
        )
        
    except TMSAPIException as e:
        return TokenValidationResponse(
            valid=False,
            user=None,
            message=f"Token validation failed: {str(e)}"
        )
    except Exception as e:
        return TokenValidationResponse(
            valid=False,
            user=None,
            message=f"Validation error: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_authenticated_user(
    authorization: str = Header(..., description="Bearer token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user (alternative endpoint).
    
    This is an alias to `/api/v1/users/me` for convenience.
    Validates token and returns full user profile.
    
    **Authentication:** Required (Bearer token in Authorization header)
    
    **Headers:**
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```
    
    **Returns:** Full user profile with local settings
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'"
        )

    token = authorization.split(" ")[1]

    try:
        user_service = UserService(db)
        user = await user_service.get_current_user(token)
        return user
    except TMSAPIException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch user from TMS: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/logout")
async def logout():
    """
    Logout endpoint (placeholder).
    
    Since this system uses TMS tokens, logout is handled client-side
    by discarding the token. This endpoint exists for API completeness.
    
    **Note:** In a production system, you might want to maintain a
    token blacklist or notify TMS of logout events.
    
    **Returns:**
    ```json
    {
        "success": true,
        "message": "Logged out successfully"
    }
    ```
    """
    return {
        "success": True,
        "message": "Logged out successfully. Please discard your token client-side."
    }


@router.get("/health")
async def auth_health_check():
    """
    Authentication service health check.
    
    Verifies connectivity to TMS API.
    
    **Returns:**
    ```json
    {
        "status": "healthy",
        "tms_connected": true,
        "message": "Authentication service is operational"
    }
    ```
    """
    try:
        tms_healthy = await tms_client.health_check()
        
        return {
            "status": "healthy" if tms_healthy else "degraded",
            "tms_connected": tms_healthy,
            "message": "Authentication service is operational" if tms_healthy else "TMS connection issues detected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "tms_connected": False,
            "message": f"Authentication service error: {str(e)}"
        }