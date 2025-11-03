"""
User Management API Client for integrating with GCGC Team Management System.
Handles user authentication, user data fetching, and communication with the
GCGC Team Management System for user identity and authorization.
"""
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings
from app.core.cache import cache_user_data, get_cached_user_data


class TMSAPIException(Exception):
    """Exception raised for TMS API errors."""
    pass


class TMSClient:
    """
    Client for communicating with GCGC Team Management System API.

    This client handles all interactions with the User Management System,
    including user authentication, profile fetching, and user search.

    Note: "TMS" in the class name refers to the Team Management System (GCGC),
    not to be confused with the Team Messaging System.
    """

    def __init__(self):
        """Initialize User Management API client."""
        self.base_url = settings.user_management_api_url.rstrip("/")
        self.api_key = settings.user_management_api_key
        self.timeout = settings.user_management_api_timeout

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for User Management API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def authenticate_with_credentials(self, email: str, password: str) -> str:
        """
        Authenticate with GCGC using email and password, get JWT token.

        This handles the complete server-to-server authentication flow:
        1. POST credentials to GCGC signin endpoint
        2. Retrieve session cookies
        3. Use cookies to GET JWT token from /api/v1/auth/token

        Args:
            email: User email address
            password: User password

        Returns:
            JWT token string

        Raises:
            TMSAPIException: If authentication fails

        Example:
            ```python
            token = await tms_client.authenticate_with_credentials(
                "user@example.com",
                "password123"
            )
            ```
        """
        # Create client with cookie persistence (httpx automatically maintains cookies)
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,  # Follow redirects to complete auth flow
        ) as client:
            try:
                # Step 1: Authenticate with GCGC callback endpoint (not signin)
                # NextAuth's callback endpoint is the one that actually creates sessions
                signin_response = await client.post(
                    f"{self.base_url}/api/auth/callback/credentials",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "username": email,  # CredentialsProvider expects 'username'
                        "password": password,
                        "callbackUrl": f"{self.base_url}/",  # Same-domain callback URL
                    }
                )

                # Debug: Log cookies received
                print(f"[AUTH DEBUG] Signin response status: {signin_response.status_code}")
                print(f"[AUTH DEBUG] Cookies in jar: {list(client.cookies.jar)}")
                for cookie in client.cookies.jar:
                    print(f"  - {cookie.name}={cookie.value[:20]}... (domain={cookie.domain}, path={cookie.path})")

                if not signin_response.is_success:
                    error_data = signin_response.text
                    raise TMSAPIException(f"Authentication failed: {error_data[:200]}")

                # Step 2: Get JWT token using the session cookies
                token_response = await client.get(
                    f"{self.base_url}/api/v1/auth/token"
                )

                # Debug: Log request cookies
                request_cookies = token_response.request.headers.get("cookie", "No cookies sent!")
                print(f"[AUTH DEBUG] Token request cookies: {request_cookies}")
                print(f"[AUTH DEBUG] Token response status: {token_response.status_code}")

                # Check if we got redirected (session not established)
                if token_response.status_code in [301, 302, 303, 307, 308]:
                    location = token_response.headers.get("location", "")
                    raise TMSAPIException(
                        f"Session not established after signin. Redirected to: {location}. "
                        f"Cookies in jar: {list(client.cookies.jar)}"
                    )

                if not token_response.is_success:
                    raise TMSAPIException(
                        f"Failed to get token from GCGC (status {token_response.status_code}): "
                        f"{token_response.text[:200]}"
                    )

                token_data = token_response.json()
                jwt_token = token_data.get("token")

                if not jwt_token:
                    raise TMSAPIException("No token in response from GCGC")

                return jwt_token

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise TMSAPIException("Invalid email or password")
                raise TMSAPIException(f"GCGC authentication failed: {e.response.text[:200]}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"GCGC API unavailable: {str(e)}")

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate user token with GCGC Team Management System.

        Args:
            token: JWT token to validate

        Returns:
            User information from GCGC

        Raises:
            TMSAPIException: If validation fails

        Example:
            ```python
            user_info = await tms_client.validate_token(token)
            tms_user_id = user_info["tms_user_id"]
            ```
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/auth/validate",
                    headers=self._get_headers(),
                    json={"token": token}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise TMSAPIException(f"Token validation failed: {e.response.text}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"TMS API request failed: {str(e)}")

    async def get_current_user_from_tms(
        self,
        token: Optional[str] = None,
        use_cache: bool = True,
        cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get current authenticated user from GCGC /api/v1/users/me.
        Supports both Bearer token and session cookie authentication.

        Args:
            token: User's JWT token or session token (optional if cookies provided)
            use_cache: Whether to use cache (default: True)
            cookies: Session cookies to forward to TMS (for NextAuth session-based auth)

        Returns:
            Current user data dictionary from GCGC

        Raises:
            TMSAPIException: If token invalid or API error

        Example:
            ```python
            # With Bearer token:
            user = await tms_client.get_current_user_from_tms(token="jwt_token")

            # With session cookies:
            user = await tms_client.get_current_user_from_tms(cookies=request.cookies)
            ```
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            try:
                headers = {"Content-Type": "application/json"}

                # Priority 1: Use session cookies if provided (for NextAuth)
                # Priority 2: Use token as Bearer auth (for JWT tokens)
                if cookies:
                    # Session-based auth: Forward cookies to TMS
                    response = await client.get(
                        f"{self.base_url}/api/v1/users/me",
                        headers=headers,
                        cookies=cookies
                    )
                elif token:
                    # Token-based auth: Use Bearer token
                    headers["Authorization"] = f"Bearer {token}"
                    response = await client.get(
                        f"{self.base_url}/api/v1/users/me",
                        headers=headers
                    )
                else:
                    raise TMSAPIException("Either token or cookies must be provided")

                # Check for redirects (common when session is invalid)
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get("location", "")
                    if "signin" in location.lower() or "login" in location.lower():
                        raise TMSAPIException("Session expired or invalid - redirected to login")
                    raise TMSAPIException(f"Unexpected redirect to: {location}")

                response.raise_for_status()
                user_data = response.json()

                # Cache the result using TMS user ID
                if use_cache and "id" in user_data:
                    await cache_user_data(user_data["id"], user_data)

                return user_data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise TMSAPIException("Invalid or expired authentication")
                # Handle HTML redirect responses
                error_text = e.response.text
                if "/auth/signin" in error_text or "/signin" in error_text:
                    raise TMSAPIException("Session expired - please login again")
                raise TMSAPIException(f"Failed to fetch current user: {error_text[:200]}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"TMS API unavailable: {str(e)}")

    async def get_user(self, tms_user_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get user data from GCGC /api/v1/users/{id}.
        Returns public user profile.

        Args:
            tms_user_id: GCGC user ID
            use_cache: Whether to use cache (default: True)

        Returns:
            User data dictionary from GCGC

        Raises:
            TMSAPIException: If user not found or API error

        Example:
            ```python
            user = await tms_client.get_user("123")
            username = user["username"]
            email = user["email"]
            ```
        """
        # Check cache first
        if use_cache:
            cached_user = await get_cached_user_data(tms_user_id)
            if cached_user:
                return cached_user

        # Fetch from TMS API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/users/{tms_user_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                user_data = response.json()

                # Cache the result
                if use_cache:
                    await cache_user_data(tms_user_id, user_data)

                return user_data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise TMSAPIException(f"User {tms_user_id} not found")
                raise TMSAPIException(f"Failed to fetch user: {e.response.text}")
            except httpx.RequestError as e:
                # If TMS is down, try to use cache even if use_cache=False
                cached_user = await get_cached_user_data(tms_user_id)
                if cached_user:
                    return cached_user
                raise TMSAPIException(f"TMS API unavailable: {str(e)}")

    async def get_users(self, tms_user_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple users from TMS in a single request (batch fetch).
        OPTIMIZED: Check cache first, only fetch missing users from API.

        Args:
            tms_user_ids: List of TMS user IDs

        Returns:
            List of user data dictionaries

        Raises:
            TMSAPIException: If API error

        Example:
            ```python
            users = await tms_client.get_users(["123", "456", "789"])
            for user in users:
                print(user["username"])
            ```
        """
        if not tms_user_ids:
            return []

        # Check cache first for all users
        cached_users = []
        uncached_ids = []

        for user_id in tms_user_ids:
            cached = await get_cached_user_data(user_id)
            if cached:
                cached_users.append(cached)
            else:
                uncached_ids.append(user_id)

        # If all users are cached, return early
        if not uncached_ids:
            return cached_users

        # Fetch only uncached users from API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/users/batch",
                    headers=self._get_headers(),
                    json={"user_ids": uncached_ids}
                )
                response.raise_for_status()
                fetched_users = response.json()

                # Cache each newly fetched user (handle both "id" and "tms_user_id" fields)
                for user in fetched_users:
                    user_id_key = user.get("id") or user.get("tms_user_id")
                    if user_id_key:
                        await cache_user_data(user_id_key, user)

                # Combine cached + fetched users
                return cached_users + fetched_users

            except httpx.HTTPStatusError as e:
                # If batch fetch fails, return whatever we have from cache
                if cached_users:
                    print(f"Warning: Batch fetch failed, returning {len(cached_users)} cached users")
                    return cached_users
                raise TMSAPIException(f"Failed to fetch users: {e.response.text}")
            except httpx.RequestError as e:
                # If TMS is down, return cached users if available
                if cached_users:
                    print(f"Warning: TMS unavailable, returning {len(cached_users)} cached users")
                    return cached_users
                raise TMSAPIException(f"TMS API request failed: {str(e)}")

    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            New access and refresh tokens

        Raises:
            TMSAPIException: If refresh fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/auth/refresh",
                    headers=self._get_headers(),
                    json={"refresh_token": refresh_token}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise TMSAPIException(f"Token refresh failed: {e.response.text}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"TMS API request failed: {str(e)}")

    async def search_users(
        self,
        query: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search users from GCGC /api/v1/users/search.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 20, max: 100)

        Returns:
            Search results with list of users from GCGC

        Raises:
            TMSAPIException: If API error

        Example:
            ```python
            results = await tms_client.search_users("john", limit=10)
            users = results["users"]
            for user in users:
                print(user["name"], user["email"])
            ```
        """
        if not query or len(query.strip()) == 0:
            return {"users": []}

        # Enforce limits
        if limit > 100:
            limit = 100
        elif limit < 1:
            limit = 1

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/users/search",
                    headers=self._get_headers(),
                    params={"q": query.strip(), "limit": limit}
                )
                response.raise_for_status()
                search_results = response.json()

                # Cache each user from search results
                if "users" in search_results:
                    for user in search_results["users"]:
                        if "id" in user:
                            await cache_user_data(user["id"], user)

                return search_results

            except httpx.HTTPStatusError as e:
                raise TMSAPIException(f"Failed to search users: {e.response.text}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"TMS API request failed: {str(e)}")

    async def get_user_by_id_with_api_key(
        self,
        user_id: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get user by ID using API Key authentication (server-to-server).
        This is the PREFERRED method for backend-to-TMS communication.

        Args:
            user_id: Team Management System user ID
            use_cache: Whether to check cache first (default: True)

        Returns:
            User data dictionary

        Raises:
            TMSAPIException: If user not found or API error

        Example:
            ```python
            user = await tms_client.get_user_by_id_with_api_key("user-123")
            print(user["displayName"], user["email"])
            ```
        """
        # Check cache first
        if use_cache:
            cached_user = await get_cached_user_data(user_id)
            if cached_user:
                return cached_user

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Use API Key for server-to-server authentication
                headers = {
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                }

                response = await client.get(
                    f"{self.base_url}/api/v1/users/{user_id}",
                    headers=headers
                )

                if response.status_code == 404:
                    raise TMSAPIException(f"User {user_id} not found in Team Management System")

                if response.status_code != 200:
                    raise TMSAPIException(
                        f"Team Management API error: {response.status_code} - {response.text}"
                    )

                user_data = response.json()

                # Cache the user data (uses default TTL from settings)
                await cache_user_data(user_id, user_data)

                return user_data

            except httpx.RequestError as e:
                raise TMSAPIException(f"Failed to connect to Team Management System: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if GCGC User Management API is available.

        Returns:
            True if GCGC is healthy, False otherwise
        """
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self._get_headers()
                )
                return response.status_code == 200
            except (httpx.HTTPStatusError, httpx.RequestError):
                return False


# Global User Management client instance
# Note: Named "tms_client" for backward compatibility
tms_client = TMSClient()
