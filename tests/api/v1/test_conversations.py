"""
Integration tests for Conversation API endpoints.
Tests API routes for conversation operations.
"""
import pytest
from uuid import uuid4

from app.models.conversation import ConversationType, ConversationRole


class TestConversationAPI:
    """Test conversation API endpoints."""

    async def test_create_group_conversation(
        self, client, auth_headers, test_user, test_user_2, mocker
    ):
        """Test creating a group conversation via API."""
        # Mock TMS client
        mock_tms = mocker.patch("app.core.tms_client.tms_client.get_users")
        mock_tms.return_value = [
            {"tms_user_id": "test_user_123", "username": "testuser1"},
            {"tms_user_id": "test_user_456", "username": "testuser2"}
        ]

        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        response = await client.post(
            "/api/v1/conversations/",
            headers=auth_headers,
            json={
                "type": "group",
                "name": "Test Group",
                "avatar_url": "https://example.com/avatar.jpg",
                "member_ids": [str(test_user_2.id)]
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "group"
        assert data["name"] == "Test Group"
        assert data["member_count"] == 2

    async def test_create_dm_conversation(
        self, client, auth_headers, test_user, test_user_2, mocker
    ):
        """Test creating a DM conversation via API."""
        # Mock TMS client
        mock_tms = mocker.patch("app.core.tms_client.tms_client.get_users")
        mock_tms.return_value = [
            {"tms_user_id": "test_user_123", "username": "testuser1"},
            {"tms_user_id": "test_user_456", "username": "testuser2"}
        ]

        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        response = await client.post(
            "/api/v1/conversations/",
            headers=auth_headers,
            json={
                "type": "dm",
                "member_ids": [str(test_user_2.id)]
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "dm"
        assert data["name"] is None
        assert data["member_count"] == 2

    async def test_create_group_without_name_fails(
        self, client, auth_headers, test_user_2
    ):
        """Test creating a group without name fails via API."""
        response = await client.post(
            "/api/v1/conversations/",
            headers=auth_headers,
            json={
                "type": "group",
                "member_ids": [str(test_user_2.id)]
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_get_user_conversations(
        self, client, auth_headers, test_user, test_conversation, mocker
    ):
        """Test getting user's conversations via API."""
        # Mock TMS client
        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        response = await client.get(
            "/api/v1/conversations/",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == str(test_conversation.id)

    async def test_get_conversation_by_id(
        self, client, auth_headers, test_user, test_conversation, mocker
    ):
        """Test getting a conversation by ID via API."""
        # Mock TMS client
        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        response = await client.get(
            f"/api/v1/conversations/{test_conversation.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_conversation.id)
        assert data["type"] == test_conversation.type
        assert data["name"] == test_conversation.name

    async def test_get_conversation_not_member_fails(
        self, client, auth_headers, test_conversation, db_session, mocker
    ):
        """Test getting a conversation as non-member fails via API."""
        # Create a non-member user
        from app.models.user import User

        non_member = User(tms_user_id="non_member_999", settings_json={})
        db_session.add(non_member)
        await db_session.commit()

        # Mock auth to return non-member
        mock_auth = mocker.patch("app.dependencies.get_current_user")
        mock_auth.return_value = {"tms_user_id": "non_member_999"}

        response = await client.get(
            f"/api/v1/conversations/{test_conversation.id}",
            headers=auth_headers
        )

        assert response.status_code == 403

    async def test_update_conversation(
        self, client, auth_headers, test_user, test_conversation, db_session, mocker
    ):
        """Test updating a conversation via API."""
        # Make test_user admin
        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        # Mock TMS client
        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        response = await client.put(
            f"/api/v1/conversations/{test_conversation.id}",
            headers=auth_headers,
            json={
                "name": "Updated Group Name"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Group Name"

    async def test_add_members_to_conversation(
        self, client, auth_headers, test_user, test_conversation, db_session, mocker
    ):
        """Test adding members to a conversation via API."""
        # Create third user
        from app.models.user import User

        user3 = User(tms_user_id="test_user_789", settings_json={})
        db_session.add(user3)
        await db_session.commit()
        await db_session.refresh(user3)

        # Make test_user admin
        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        # Mock TMS client
        mock_tms = mocker.patch("app.core.tms_client.tms_client.get_users")
        mock_tms.return_value = [{"tms_user_id": "test_user_789"}]

        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/members",
            headers=auth_headers,
            json={
                "user_ids": [str(user3.id)]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["affected_count"] == 1

    async def test_remove_member_from_conversation(
        self, client, auth_headers, test_user, test_user_2, test_conversation, db_session
    ):
        """Test removing a member from a conversation via API."""
        # Make test_user admin
        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/conversations/{test_conversation.id}/members/{test_user_2.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_leave_conversation(
        self, client, auth_headers, test_user, test_conversation
    ):
        """Test leaving a conversation via API."""
        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/leave",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_update_conversation_settings(
        self, client, auth_headers, test_user, test_conversation
    ):
        """Test updating conversation settings via API."""
        response = await client.put(
            f"/api/v1/conversations/{test_conversation.id}/settings",
            headers=auth_headers,
            json={
                "is_muted": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_muted"] is True

    async def test_mark_conversation_read(
        self, client, auth_headers, test_user, test_conversation
    ):
        """Test marking conversation as read via API."""
        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/mark-read",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "last_read_at" in data

    async def test_conversation_pagination(
        self, client, auth_headers, test_user, test_conversation, db_session, mocker
    ):
        """Test conversation pagination via API."""
        # Create additional conversations
        from app.models.conversation import Conversation, ConversationMember, ConversationType

        for i in range(3):
            conv = Conversation(
                type=ConversationType.GROUP,
                name=f"Test Group {i}",
                created_by=test_user.id
            )
            db_session.add(conv)
            await db_session.flush()

            member = ConversationMember(
                conversation_id=conv.id,
                user_id=test_user.id
            )
            db_session.add(member)

        await db_session.commit()

        # Mock TMS client
        mock_get_user = mocker.patch("app.core.tms_client.tms_client.get_user")
        mock_get_user.return_value = {"tms_user_id": "test_user_123", "username": "testuser1"}

        # Get first page
        response = await client.get(
            "/api/v1/conversations/?limit=2",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["pagination"]["has_more"] is True
        assert data["pagination"]["next_cursor"] is not None

        # Get second page
        cursor = data["pagination"]["next_cursor"]
        response = await client.get(
            f"/api/v1/conversations/?limit=2&cursor={cursor}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 2

    async def test_unauthorized_request_fails(self, unauth_client, test_conversation):
        """Test requests without auth fail."""
        response = await unauth_client.get(
            f"/api/v1/conversations/{test_conversation.id}"
        )

        assert response.status_code == 401 or response.status_code == 403
