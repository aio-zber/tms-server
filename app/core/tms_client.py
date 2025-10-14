"""
TMS API Client for integrating with Team Management System.
Handles user authentication, user data fetching, and TMS communication.
"""
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings
from app.core.cache import cache_user_data, get_cached_user_data


class TMSAPIException(Exception):
    """Exception raised for TMS API errors."""
    pass


class TMSClient:
    """Client for communicating with TMS API."""

    def __init__(self):
        """Initialize TMS client."""
        self.base_url = settings.tms_api_url.rstrip("/")
        self.api_key = settings.tms_api_key
        self.timeout = settings.tms_api_timeout

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for TMS API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate user token with TMS.

        Args:
            token: JWT token to validate

        Returns:
            User information from TMS

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

    async def get_current_user_from_tms(self, token: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get current authenticated user from TMS /api/v1/users/me.
        Uses the user's token to fetch their full profile.

        Args:
            token: User's JWT token
            use_cache: Whether to use cache (default: True)

        Returns:
            Current user data dictionary (TMSCurrentUserSchema)

        Raises:
            TMSAPIException: If token invalid or API error

        Example:
            ```python
            user = await tms_client.get_current_user_from_tms(token)
            user_id = user["id"]
            email = user["email"]
            ```
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Use user's token, not API key
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                response = await client.get(
                    f"{self.base_url}/api/v1/users/me",
                    headers=headers
                )
                response.raise_for_status()
                user_data = response.json()

                # Cache the result using TMS user ID
                if use_cache and "id" in user_data:
                    await cache_user_data(user_data["id"], user_data)

                return user_data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise TMSAPIException("Invalid or expired token")
                raise TMSAPIException(f"Failed to fetch current user: {e.response.text}")
            except httpx.RequestError as e:
                raise TMSAPIException(f"TMS API unavailable: {str(e)}")

    async def get_user(self, tms_user_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get user data from TMS /api/v1/users/{id}.
        Returns public user profile (TMSPublicUserSchema).

        Args:
            tms_user_id: TMS user ID
            use_cache: Whether to use cache (default: True)

        Returns:
            User data dictionary

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
        Search users from TMS /api/v1/users/search.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 20, max: 100)

        Returns:
            UserSearchResponse with list of users

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
        Check if TMS API is available.

        Returns:
            True if TMS is healthy, False otherwise
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


# Global TMS client instance
tms_client = TMSClient()
