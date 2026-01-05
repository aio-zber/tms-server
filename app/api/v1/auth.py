"""
Authentication API endpoints.
Provides login functionality and token validation using TMS integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.services.user_service import UserService
from app.core.tms_client import tms_client, TMSAPIException
from app.core.security import decode_nextauth_token, SecurityException
from app.schemas.user import UserResponse
from app.repositories.user_repo import UserRepository
from app.core.sso_codes import generate_sso_code, validate_sso_code

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema for proxy authentication."""
    token: str = Field(..., description="TMS JWT token to validate")


class CredentialsLoginRequest(BaseModel):
    """Login request schema with email and password."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Login response schema."""
    success: bool
    user: UserResponse
    token: str
    message: str = "Login successful"


class TokenValidationResponse(BaseModel):
    """Token validation response schema."""
    valid: bool
    user: Optional[UserResponse] = None
    message: str


class GCGCSessionValidationRequest(BaseModel):
    """GCGC session validation request schema."""
    gcgc_token: str = Field(..., description="GCGC NextAuth session token")


class GCGCSessionValidationResponse(BaseModel):
    """GCGC session validation response schema."""
    valid: bool
    user: Optional[dict] = Field(None, description="Current GCGC user info (id and email)")
    message: str


@router.post("/login/credentials", response_model=LoginResponse)
async def login_with_credentials(
    credentials: CredentialsLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate with GCGC using email and password, return JWT token.

    This endpoint handles the complete authentication flow:
    1. Authenticate with GCGC using credentials
    2. Get JWT token from GCGC
    3. Sync user data to local database
    4. Return JWT token and user profile

    **Flow:**
    1. Validate credentials with GCGC
    2. Get JWT token from GCGC
    3. Sync user to local database
    4. Return token and user data to client

    **Request Body:**
    ```json
    {
        "email": "user@example.com",
        "password": "password123"
    }
    ```

    **Returns:** JWT token and user profile

    **Errors:**
    - 401: Invalid credentials
    - 503: GCGC service unavailable
    - 500: Internal server error
    """
    try:
        # Authenticate with GCGC and get token server-to-server
        token = await tms_client.authenticate_with_credentials(
            credentials.email,
            credentials.password
        )

        # Decode token to get user data
        token_payload = decode_nextauth_token(token)

        # Extract user data from token
        tms_user_id = token_payload.get("id")
        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain user ID"
            )

        # Prepare user data from token for syncing
        tms_user_data = {
            "id": tms_user_id,
            "email": token_payload.get("email"),
            "name": token_payload.get("name"),
            "role": token_payload.get("role"),
            "hierarchyLevel": token_payload.get("hierarchyLevel"),
            "image": token_payload.get("image"),
        }

        # Sync user to local database
        user_repo = UserRepository(db)
        user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
        await db.commit()
        await db.refresh(user)  # Refresh to ensure all attributes are loaded

        # Build user response
        user_service = UserService(db)
        user_response = user_service._map_user_to_response(user, tms_user_data)

        return LoginResponse(
            success=True,
            user=user_response,
            token=token,  # Return the JWT token to client
            message="Login successful"
        )

    except TMSAPIException as e:
        # GCGC authentication failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED if "401" in str(e) or "Unauthorized" in str(e) else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "authentication_failed",
                "message": str(e),
                "hint": "Please check your email and password"
            }
        )
    except SecurityException as e:
        # Token validation failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_failed",
                "message": str(e),
                "hint": "Authentication succeeded but token validation failed"
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Credentials login error: {type(e).__name__}: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Failed to process login request",
                "type": type(e).__name__,
                "hint": "Please contact support if the issue persists"
            }
        )


@router.post("/login/sso", response_model=LoginResponse)
async def sso_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    gcgc_session_token: Optional[str] = Header(None, alias="X-GCGC-Session-Token")
):
    """
    SSO login using GCGC NextAuth JWT token.

    This endpoint enables seamless Single Sign-On (SSO) from GCGC to TMS.
    It accepts a GCGC NextAuth JWT token (not a session cookie), decodes it
    locally using the shared NEXTAUTH_SECRET, and returns user data.

    **Flow:**
    1. Receive GCGC JWT token via X-GCGC-Session-Token header
    2. Decode and validate JWT locally using NEXTAUTH_SECRET (no API call)
    3. Extract user data from JWT payload
    4. Sync user data to local database
    5. Return the GCGC JWT token for API access

    **Important:** The token is a JWT signed with NEXTAUTH_SECRET,
    not a NextAuth session cookie. It's decoded locally, not validated with GCGC.

    **Headers:**
    ```
    X-GCGC-Session-Token: <jwt-token-from-gcgc-sso>
    ```

    **Returns:** GCGC JWT token and user profile

    **Errors:**
    - 401: Invalid, expired, or missing JWT token
    - 500: Internal server error

    **Usage:**
    This endpoint is called automatically by TMS-Client after GCGC SSO redirect,
    enabling transparent authentication without additional API calls to GCGC.
    """
    if not gcgc_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_session_token",
                "message": "No GCGC session token provided",
                "hint": "Ensure you're logged into GCGC and have a valid session"
            }
        )

    try:
        import logging
        logger = logging.getLogger(__name__)

        # Decode and validate GCGC JWT token locally using shared NEXTAUTH_SECRET
        # This is faster and more reliable than calling GCGC API
        logger.info(f"🔐 SSO Login: Received GCGC JWT token (length: {len(gcgc_session_token)})")
        logger.debug(f"🔐 SSO Login: Token prefix: {gcgc_session_token[:50]}...")

        from app.core.security import decode_nextauth_token, SecurityException

        jwt_payload = decode_nextauth_token(gcgc_session_token)
        logger.info(f"✅ SSO Login: JWT decoded successfully for user {jwt_payload.get('email')}")
        logger.debug(f"🔐 SSO Login: JWT payload: {jwt_payload}")

        # Extract user data from JWT payload
        tms_user_id = jwt_payload.get("id")
        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token does not contain user ID"
            )

        # Build user data dictionary from JWT claims
        # JWT tokens from GCGC contain: id, email, name, role, hierarchyLevel, image, iat, exp
        tms_user_data = {
            "id": jwt_payload.get("id"),
            "email": jwt_payload.get("email"),
            "name": jwt_payload.get("name"),
            "username": jwt_payload.get("email", "").split("@")[0] if jwt_payload.get("email") else "user",
            "role": jwt_payload.get("role", "MEMBER"),
            "hierarchyLevel": jwt_payload.get("hierarchyLevel"),
            "image": jwt_payload.get("image"),
            "isActive": True,  # JWT tokens are only issued for active users
        }

        # Sync user to local database
        user_repo = UserRepository(db)
        user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
        await db.commit()
        await db.refresh(user)

        # Build user response
        user_service = UserService(db)
        user_response = user_service._map_user_to_response(user, tms_user_data)

        # Return the GCGC session token as the JWT token
        # TMS-Client will store this and use it for subsequent API calls
        return LoginResponse(
            success=True,
            user=user_response,
            token=gcgc_session_token,  # Use GCGC token directly
            message="SSO login successful"
        )

    except SecurityException as e:
        # JWT decoding failed (invalid signature, expired token, etc.)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ SSO Login: JWT decode failed: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_jwt_token",
                "message": str(e),
                "hint": "Your GCGC session has expired. Please log in again."
            }
        )
    except TMSAPIException as e:
        # This should not happen anymore since we're not calling GCGC API
        # Kept for backwards compatibility
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED if "401" in str(e) or "Unauthorized" in str(e) else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "sso_authentication_failed",
                "message": str(e),
                "hint": "Your GCGC session may have expired. Please log in to GCGC again."
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SSO login error: {type(e).__name__}: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Failed to process SSO login request",
                "type": type(e).__name__,
                "hint": "Please contact support if the issue persists"
            }
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate NextAuth JWT token and sync user data.

    This endpoint accepts JWT tokens generated by GCGC TMS's /api/v1/auth/token endpoint.
    The token contains all user information and is signed with NEXTAUTH_SECRET.

    **Flow:**
    1. Decode and validate NextAuth JWT token
    2. Extract user information from token
    3. Sync user data to local database
    4. Return user profile

    **Request Body:**
    ```json
    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    **Returns:** User profile if authentication is valid

    **Errors:**
    - 401: Invalid or expired token
    - 500: Internal server error
    """
    try:
        # Decode the NextAuth JWT token
        token_payload = decode_nextauth_token(login_request.token)

        # Extract user data from token
        tms_user_id = token_payload.get("id")
        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain user ID"
            )

        # Prepare user data from token for syncing
        tms_user_data = {
            "id": tms_user_id,
            "email": token_payload.get("email"),
            "name": token_payload.get("name"),
            "role": token_payload.get("role"),
            "hierarchyLevel": token_payload.get("hierarchyLevel"),
            "image": token_payload.get("image"),
        }

        # Sync user to local database
        user_repo = UserRepository(db)
        user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
        await db.commit()
        await db.refresh(user)  # Refresh to ensure all attributes are loaded

        # Build user response
        user_service = UserService(db)
        user_response = user_service._map_user_to_response(user, tms_user_data)

        return LoginResponse(
            success=True,
            user=user_response,
            token=login_request.token,  # Return the token back to client
            message="Login successful"
        )

    except SecurityException as e:
        # Enhanced error message for token validation failures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_failed",
                "message": str(e),
                "hint": "Please ensure you're using a valid JWT token from GCGC authentication"
            }
        )
    except Exception as e:
        # Enhanced error message for unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Login error: {type(e).__name__}: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Failed to process login request",
                "type": type(e).__name__,
                "hint": "Please contact support if the issue persists"
            }
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
        # Distinguish between authentication failures and network errors
        error_msg = str(e).lower()

        # If GCGC explicitly rejected the token (401), it's invalid
        if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
            return TokenValidationResponse(
                valid=False,
                user=None,
                message="Token is invalid or expired"
            )

        # For network errors, service unavailable, timeouts - raise 503
        # Client will NOT logout for 503 errors (handles gracefully)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "gcgc_unavailable",
                "message": "Unable to validate token - GCGC service temporarily unavailable",
                "hint": "This is a temporary issue. Your session remains valid."
            }
        )
    except Exception as e:
        # Unexpected errors - treat as service unavailable to prevent logout
        logger.error(f"Unexpected error during token validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "validation_error",
                "message": "Unable to validate token due to unexpected error",
                "hint": "This is a temporary issue. Your session remains valid."
            }
        )


@router.post("/validate-gcgc-session", response_model=GCGCSessionValidationResponse)
async def validate_gcgc_session(
    request: GCGCSessionValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate GCGC session token and return current user ID.

    Used by TMS-Client to detect account switches on page load.
    When user closes TMS tab, logs out of GCGC, and logs in as different user,
    this endpoint allows TMS to detect the mismatch and clear the old session.

    **Request Body:**
    ```json
    {
        "gcgc_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    **Returns:**
    ```json
    {
        "valid": true,
        "user": {
            "id": "cmgoip1nt0001s89pzkw7bzlg",
            "email": "user@example.com"
        },
        "message": "GCGC session is valid"
    }
    ```

    **Use Case:**
    - TMS-Client calls this on page load to verify GCGC session matches TMS session
    - If user IDs don't match, TMS clears old session and redirects to SSO

    **Note:** This endpoint only validates and returns user ID, doesn't sync or login
    """
    try:
        # Validate GCGC session token and get current user
        tms_user_data = await tms_client.get_current_user_from_tms(request.gcgc_token, use_cache=False)

        return GCGCSessionValidationResponse(
            valid=True,
            user={
                "id": tms_user_data["id"],
                "email": tms_user_data.get("email", "")
            },
            message="GCGC session is valid"
        )

    except TMSAPIException as e:
        # GCGC rejected the token or user not found
        error_msg = str(e).lower()

        if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
            return GCGCSessionValidationResponse(
                valid=False,
                user=None,
                message="GCGC session is invalid or expired"
            )

        # For network errors - return invalid to trigger re-auth (safer than 503)
        logger.warning(f"GCGC validation failed (network error): {str(e)}")
        return GCGCSessionValidationResponse(
            valid=False,
            user=None,
            message="Unable to validate GCGC session"
        )

    except Exception as e:
        # Unexpected errors - return invalid to be safe
        logger.error(f"Unexpected error during GCGC session validation: {str(e)}")
        return GCGCSessionValidationResponse(
            valid=False,
            user=None,
            message="GCGC session validation failed"
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


class SSOCodeExchangeRequest(BaseModel):
    """SSO code exchange request schema."""
    code: str = Field(..., description="One-time SSO code")


@router.get("/sso/check")
async def sso_check(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    SSO Check Endpoint - Server-to-Server SSO Flow Initiator.

    This endpoint initiates the SSO flow by checking if the user has a valid
    GCGC session. It acts as a proxy between TMS-Client and GCGC, enabling
    server-to-server authentication without cross-domain cookie issues.

    **Security Note:**
    The redirect_uri is hardcoded in configuration (settings.tms_client_url)
    to prevent open redirect attacks (CWE-601). This ensures SSO codes are
    only sent to the legitimate TMS-Client instance, not attacker-controlled URLs.

    **Flow:**
    1. TMS-Client redirects browser to this endpoint
    2. TMS-Server receives request WITH all browser cookies (including GCGC cookies)
    3. If GCGC cookie found → Validate with GCGC → Generate SSO code → Redirect back
    4. If no GCGC cookie → Redirect to GCGC login → GCGC redirects to /sso/callback

    **Query Parameters:**
    - `redirect_uri`: TMS-Client URL to redirect back to after SSO check

    **Returns:**
    - Redirect to TMS-Client with `sso_code` parameter if authenticated
    - Redirect to GCGC login if not authenticated

    **Usage:**
    ```
    GET /api/v1/auth/sso/check?redirect_uri=https://tms-client.example.com
    ```

    **Why This Works:**
    When browser redirects to TMS-Server, it sends ALL cookies including GCGC cookies
    (if GCGC sets cookies with proper attributes like SameSite=None or same parent domain).
    TMS-Server can read these cookies server-side, avoiding cross-domain JavaScript restrictions.
    """
    import logging
    logger = logging.getLogger(__name__)
    from app.config import settings

    # Use hardcoded redirect_uri from config (NOT from query params)
    # This prevents open redirect attacks where attackers could steal SSO codes
    redirect_uri = settings.get_tms_client_url()

    # Security logging: warn if someone tries to pass redirect_uri (for monitoring)
    if request.query_params.get("redirect_uri"):
        logger.warning(
            f"⚠️ Security: Ignored user-supplied redirect_uri={request.query_params.get('redirect_uri')} "
            f"(using configured value: {redirect_uri})"
        )

    logger.info(f"🔐 SSO Check: Using configured redirect_uri: {redirect_uri}")

    # Cookie names to check (NextAuth default names)
    cookie_names = [
        "next-auth.session-token",
        "__Secure-next-auth.session-token",
        "__Host-next-auth.session-token",
        "authjs.session-token",
        "__Secure-authjs.session-token",
    ]

    # Check for GCGC session cookie
    gcgc_session_token = None
    for cookie_name in cookie_names:
        gcgc_session_token = request.cookies.get(cookie_name)
        if gcgc_session_token:
            logger.info(f"🔐 SSO Check: Found GCGC cookie: {cookie_name}")
            break

    if gcgc_session_token:
        # User has GCGC session - validate and generate code
        try:
            logger.info("🔐 SSO Check: Validating GCGC session with GCGC API...")

            # Validate GCGC session token (server-to-server)
            tms_user_data = await tms_client.get_current_user_from_session(gcgc_session_token)
            tms_user_id = tms_user_data.get("id")

            if not tms_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GCGC user data does not contain user ID"
                )

            logger.info(f"✅ SSO Check: GCGC session valid for user {tms_user_id}")

            # Sync user to local database
            user_repo = UserRepository(db)
            user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
            await db.commit()

            # Generate one-time SSO code (includes GCGC token for pass-through)
            sso_code = generate_sso_code(tms_user_id, tms_user_data, gcgc_session_token)

            logger.info(f"✅ SSO Check: Generated SSO code, redirecting to {redirect_uri}")

            # Redirect back to TMS-Client with code
            return RedirectResponse(
                url=f"{redirect_uri}?sso_code={sso_code}",
                status_code=status.HTTP_302_FOUND
            )

        except TMSAPIException as e:
            logger.warning(f"❌ SSO Check: GCGC validation failed: {str(e)}")
            # GCGC session invalid - redirect to GCGC login
            pass  # Fall through to GCGC login redirect
        except Exception as e:
            logger.error(f"❌ SSO Check: Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
            # Fall through to GCGC login redirect

    # No valid GCGC session - redirect to GCGC login
    logger.info("🔐 SSO Check: No valid GCGC session, redirecting to GCGC login")

    gcgc_login_url = os.getenv(
        "GCGC_LOGIN_URL",
        "https://tms-staging.example.com/auth/signin"
    )

    # Build callback URL for GCGC to redirect back to
    # Note: The proxy_headers_middleware in main.py ensures request.url.scheme
    # correctly reflects HTTPS from Railway's X-Forwarded-Proto header
    callback_url = f"{request.url.scheme}://{request.url.netloc}/api/v1/auth/sso/callback"

    # Properly encode the callback URL for GCGC's callbackUrl parameter
    # No need to pass redirect_uri as query param - it's hardcoded in /sso/callback endpoint
    from urllib.parse import urlencode
    gcgc_redirect_url = f"{gcgc_login_url}?{urlencode({'callbackUrl': callback_url})}"

    logger.info(f"🔐 SSO Check: Redirecting to GCGC: {gcgc_redirect_url}")

    # Redirect to GCGC login with properly encoded callback
    return RedirectResponse(
        url=gcgc_redirect_url,
        status_code=status.HTTP_302_FOUND
    )


@router.get("/sso/callback")
async def sso_callback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    SSO Callback Handler - Receives redirect from GCGC after login.

    This endpoint is called by GCGC after the user logs in. At this point,
    the browser has a GCGC session cookie. We validate it and generate an
    SSO code to pass back to TMS-Client.

    **Security Note:**
    The redirect_uri is hardcoded in configuration (settings.tms_client_url)
    to prevent open redirect attacks (CWE-601). This ensures SSO codes are
    only sent to the legitimate TMS-Client instance, not attacker-controlled URLs.

    **Flow:**
    1. User logs into GCGC
    2. GCGC redirects to this endpoint
    3. TMS-Server reads GCGC cookie from browser
    4. TMS-Server validates with GCGC (server-to-server)
    5. TMS-Server generates SSO code
    6. TMS-Server redirects to TMS-Client with code (hardcoded URL)

    **Returns:**
    - Redirect to TMS-Client with `sso_code` parameter

    **Usage:**
    ```
    # This endpoint is called automatically by GCGC after login
    GET /api/v1/auth/sso/callback
    ```
    """
    import logging
    logger = logging.getLogger(__name__)
    from app.config import settings

    # Use hardcoded redirect_uri from config (NOT from query params)
    redirect_uri = settings.get_tms_client_url()

    # Security logging: warn if someone tries to pass redirect_uri
    if request.query_params.get("redirect_uri"):
        logger.warning(
            f"⚠️ Security: Ignored user-supplied redirect_uri={request.query_params.get('redirect_uri')} "
            f"(using configured value: {redirect_uri})"
        )

    logger.info(f"🔐 SSO Callback: Using configured redirect_uri: {redirect_uri}")

    # Cookie names to check
    cookie_names = [
        "next-auth.session-token",
        "__Secure-next-auth.session-token",
        "__Host-next-auth.session-token",
        "authjs.session-token",
        "__Secure-authjs.session-token",
    ]

    # Check for GCGC session cookie
    gcgc_session_token = None
    for cookie_name in cookie_names:
        gcgc_session_token = request.cookies.get(cookie_name)
        if gcgc_session_token:
            logger.info(f"🔐 SSO Callback: Found GCGC cookie: {cookie_name}")
            break

    if not gcgc_session_token:
        logger.error("❌ SSO Callback: No GCGC session cookie found after login")
        # Redirect to TMS-Client without code (will trigger manual login)
        return RedirectResponse(
            url=redirect_uri,
            status_code=status.HTTP_302_FOUND
        )

    try:
        logger.info("🔐 SSO Callback: Validating GCGC session...")

        # Validate GCGC session token (server-to-server)
        tms_user_data = await tms_client.get_current_user_from_session(gcgc_session_token)
        tms_user_id = tms_user_data.get("id")

        if not tms_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GCGC user data does not contain user ID"
            )

        logger.info(f"✅ SSO Callback: GCGC session valid for user {tms_user_id}")

        # Sync user to local database
        user_repo = UserRepository(db)
        user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
        await db.commit()

        # Generate one-time SSO code (includes GCGC token for pass-through)
        sso_code = generate_sso_code(tms_user_id, tms_user_data, gcgc_session_token)

        logger.info(f"✅ SSO Callback: Generated SSO code, redirecting to {redirect_uri}")

        # Redirect back to TMS-Client with code
        return RedirectResponse(
            url=f"{redirect_uri}?sso_code={sso_code}",
            status_code=status.HTTP_302_FOUND
        )

    except TMSAPIException as e:
        logger.error(f"❌ SSO Callback: GCGC validation failed: {str(e)}")
        # Redirect to TMS-Client without code
        return RedirectResponse(
            url=redirect_uri,
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        logger.error(f"❌ SSO Callback: Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        # Redirect to TMS-Client without code
        return RedirectResponse(
            url=redirect_uri,
            status_code=status.HTTP_302_FOUND
        )


@router.post("/sso/exchange", response_model=LoginResponse)
async def sso_code_exchange(
    exchange_request: SSOCodeExchangeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    SSO Code Exchange - Exchange one-time code for JWT token.

    This endpoint completes the SSO flow by exchanging the one-time SSO code
    for a JWT token. The code is validated and consumed (can only be used once).

    **Flow:**
    1. TMS-Client receives SSO code from URL
    2. TMS-Client POSTs code to this endpoint
    3. TMS-Server validates code (checks expiration, usage)
    4. TMS-Server returns JWT token and user data
    5. TMS-Client stores JWT for API requests

    **Request Body:**
    ```json
    {
      "code": "abc123def456..."
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "user": {...},
      "token": "jwt-token-here",
      "message": "SSO login successful"
    }
    ```

    **Errors:**
    - 400: Invalid or expired SSO code
    - 401: Code already used
    - 500: Internal server error

    **Security:**
    - Codes expire after 5 minutes
    - Codes can only be used once
    - Codes are cryptographically random (32 characters)
    """
    import logging
    logger = logging.getLogger(__name__)

    # Validate and consume SSO code
    code_data = validate_sso_code(exchange_request.code)

    if not code_data:
        logger.warning(f"❌ SSO Exchange: Invalid or expired code")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_sso_code",
                "message": "SSO code is invalid, expired, or already used",
                "hint": "Please initiate SSO flow again"
            }
        )

    try:
        tms_user_id = code_data["user_id"]
        tms_user_data = code_data["user_data"]
        gcgc_token = code_data["gcgc_token"]

        logger.info(f"✅ SSO Exchange: Valid code for user {tms_user_id}")

        # Get or sync user from database
        user_repo = UserRepository(db)
        user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
        await db.commit()
        await db.refresh(user)

        # Build user response
        user_service = UserService(db)
        user_response = user_service._map_user_to_response(user, tms_user_data)

        # Use GCGC session token directly (Option A: Pass-through approach)
        # This maintains tight coupling with GCGC - when user logs out of GCGC,
        # they're automatically logged out of TMS (single source of truth)
        token = gcgc_token

        logger.info(f"✅ SSO Exchange: Login successful for user {tms_user_id}, returning GCGC token")

        return LoginResponse(
            success=True,
            user=user_response,
            token=token,
            message="SSO login successful"
        )

    except Exception as e:
        logger.error(f"❌ SSO Exchange: Error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Failed to process SSO code exchange",
                "type": type(e).__name__
            }
        )