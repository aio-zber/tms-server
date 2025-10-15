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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/users/batch",
                    headers=self._get_headers(),
                    json={"user_ids": tms_user_ids}
                )
                response.raise_for_status()
                users = response.json()

                # Cache each user
                for user in users:
                    if "tms_user_id" in user:
                        await cache_user_data(user["tms_user_id"], user)

                return users

            except httpx.HTTPStatusError as e:
                raise TMSAPIException(f"Failed to fetch users: {e.response.text}")
            except httpx.RequestError as e:
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
