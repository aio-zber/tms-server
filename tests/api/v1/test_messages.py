"""
Integration tests for Message API endpoints.
Tests API routes and HTTP interactions.
"""
import pytest
from uuid import uuid4


@pytest.mark.asyncio
class TestMessageAPI:
    """Test cases for Message API endpoints."""

    async def test_send_message_unauthorized(self, unauth_client):
        """Test sending a message without authentication."""
        response = await unauth_client.post(
            "/api/v1/messages/",
            json={
                "conversation_id": str(uuid4()),
                "content": "Test message",
                "type": "text"
            }
        )

        assert response.status_code == 401

    async def test_send_message_success(
        self,
        client,
        auth_headers,
        test_conversation,
        mocker
    ):
        """Test sending a message successfully."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser",
            "email": "test@example.com"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.post(
            "/api/v1/messages/",
            headers=auth_headers,
            json={
                "conversation_id": str(test_conversation.id),
                "content": "Test message",
                "type": "text",
                "metadata_json": {}
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Test message"
        assert data["type"] == "text"

    async def test_get_message_success(
        self,
        client,
        auth_headers,
        test_message,
        mocker
    ):
        """Test getting a message successfully."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.get(
            f"/api/v1/messages/{test_message.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_message.id)

    async def test_edit_message_success(
        self,
        client,
        auth_headers,
        test_message,
        mocker
    ):
        """Test editing a message successfully."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.put(
            f"/api/v1/messages/{test_message.id}",
            headers=auth_headers,
            json={"content": "Updated message"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated message"
        assert data["is_edited"] is True

    async def test_delete_message_success(
        self,
        client,
        auth_headers,
        test_message,
        mocker
    ):
        """Test deleting a message successfully."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.delete(
            f"/api/v1/messages/{test_message.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_add_reaction(
        self,
        client,
        auth_headers,
        test_message,
        mocker
    ):
        """Test adding a reaction to a message."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.post(
            f"/api/v1/messages/{test_message.id}/reactions",
            headers=auth_headers,
            json={"emoji": "👍"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["emoji"] == "👍"

    async def test_remove_reaction(
        self,
        client,
        auth_headers,
        test_message,
        mocker
    ):
        """Test removing a reaction from a message."""
        # Mock TMS client and add reaction first
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        # Add reaction
        await client.post(
            f"/api/v1/messages/{test_message.id}/reactions",
            headers=auth_headers,
            json={"emoji": "👍"}
        )

        # Remove reaction
        response = await client.delete(
            f"/api/v1/messages/{test_message.id}/reactions/👍",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_get_conversation_messages(
        self,
        client,
        auth_headers,
        test_conversation,
        mocker
    ):
        """Test getting conversation messages."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.get(
            f"/api/v1/messages/conversations/{test_conversation.id}/messages",
            headers=auth_headers,
            params={"limit": 50}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    async def test_mark_messages_read(
        self,
        client,
        auth_headers,
        test_message,
        test_conversation,
        mocker
    ):
        """Test marking messages as read."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.post(
            "/api/v1/messages/mark-read",
            headers=auth_headers,
            json={
                "message_ids": [str(test_message.id)],
                "conversation_id": str(test_conversation.id)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_search_messages(
        self,
        client,
        auth_headers,
        test_user,
        mocker
    ):
        """Test searching messages."""
        # Mock TMS client
        mock_user_data = {
            "tms_user_id": "test_user_123",
            "username": "testuser"
        }

        mocker.patch(
            "app.core.tms_client.tms_client.get_user",
            return_value=mock_user_data
        )

        response = await client.post(
            "/api/v1/messages/search",
            headers=auth_headers,
            json={
                "query": "test",
                "limit": 50
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
