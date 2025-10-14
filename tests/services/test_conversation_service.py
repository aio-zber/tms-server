"""
Unit tests for ConversationService.
Tests business logic for conversation operations.
"""
import pytest
from datetime import datetime
from uuid import UUID

from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationType, ConversationRole
from fastapi import HTTPException


class TestConversationService:
    """Test conversation service operations."""

    async def test_create_group_conversation_success(
        self, db_session, test_user, test_user_2, mocker
    ):
        """Test creating a group conversation successfully."""
        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_users = mocker.AsyncMock(return_value=[
            {"tms_user_id": "test_user_123", "username": "testuser1"},
            {"tms_user_id": "test_user_456", "username": "testuser2"}
        ])
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        conversation = await service.create_conversation(
            creator_id=test_user.id,
            type=ConversationType.GROUP,
            member_ids=[test_user_2.id],
            name="Test Group",
            avatar_url="https://example.com/avatar.jpg"
        )

        assert conversation is not None
        assert conversation["type"] == ConversationType.GROUP
        assert conversation["name"] == "Test Group"
        assert conversation["avatar_url"] == "https://example.com/avatar.jpg"
        assert str(conversation["created_by"]) == str(test_user.id)
        assert conversation["member_count"] == 2  # Creator + 1 member

    async def test_create_dm_conversation_success(
        self, db_session, test_user, test_user_2, mocker
    ):
        """Test creating a DM conversation successfully."""
        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_users = mocker.AsyncMock(return_value=[
            {"tms_user_id": "test_user_123", "username": "testuser1"},
            {"tms_user_id": "test_user_456", "username": "testuser2"}
        ])
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        conversation = await service.create_conversation(
            creator_id=test_user.id,
            type=ConversationType.DM,
            member_ids=[test_user_2.id]
        )

        assert conversation is not None
        assert conversation["type"] == ConversationType.DM
        assert conversation["name"] is None  # DMs don't have names
        assert conversation["member_count"] == 2

    async def test_create_dm_returns_existing(
        self, db_session, test_user, test_user_2, test_conversation, mocker
    ):
        """Test creating a DM returns existing conversation."""
        # Convert test_conversation to DM
        test_conversation.type = ConversationType.DM
        test_conversation.name = None
        await db_session.commit()

        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        conversation = await service.create_conversation(
            creator_id=test_user.id,
            type=ConversationType.DM,
            member_ids=[test_user_2.id]
        )

        assert conversation is not None
        assert str(conversation["id"]) == str(test_conversation.id)

    async def test_create_group_without_name_fails(
        self, db_session, test_user, test_user_2
    ):
        """Test creating a group without name fails."""
        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_conversation(
                creator_id=test_user.id,
                type=ConversationType.GROUP,
                member_ids=[test_user_2.id]
            )

        assert exc_info.value.status_code == 400
        assert "must have a name" in str(exc_info.value.detail)

    async def test_create_dm_with_wrong_member_count_fails(
        self, db_session, test_user
    ):
        """Test creating a DM with wrong member count fails."""
        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_conversation(
                creator_id=test_user.id,
                type=ConversationType.DM,
                member_ids=[]  # No other member
            )

        assert exc_info.value.status_code == 400
        assert "exactly 1 other member" in str(exc_info.value.detail)

    async def test_get_conversation_success(
        self, db_session, test_user, test_conversation, mocker
    ):
        """Test getting a conversation successfully."""
        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        conversation = await service.get_conversation(
            test_conversation.id,
            test_user.id
        )

        assert conversation is not None
        assert str(conversation["id"]) == str(test_conversation.id)
        assert conversation["type"] == test_conversation.type
        assert conversation["name"] == test_conversation.name

    async def test_get_conversation_not_member_fails(
        self, db_session, test_conversation, mocker
    ):
        """Test getting a conversation as non-member fails."""
        # Create a third user who is not a member
        from app.models.user import User

        non_member = User(tms_user_id="non_member_789", settings_json={})
        db_session.add(non_member)
        await db_session.commit()
        await db_session.refresh(non_member)

        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_conversation(test_conversation.id, non_member.id)

        assert exc_info.value.status_code == 403
        assert "not a member" in str(exc_info.value.detail)

    async def test_get_user_conversations(
        self, db_session, test_user, test_conversation, mocker
    ):
        """Test getting user's conversations."""
        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        conversations, next_cursor, has_more = await service.get_user_conversations(
            user_id=test_user.id,
            limit=50
        )

        assert len(conversations) == 1
        assert str(conversations[0]["id"]) == str(test_conversation.id)
        assert next_cursor is None
        assert has_more is False

    async def test_update_conversation_success(
        self, db_session, test_user, test_conversation, mocker
    ):
        """Test updating conversation details successfully."""
        # Mock TMS client
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_user = mocker.AsyncMock(return_value={"tms_user_id": "test_user_123", "username": "testuser1"})

        service = ConversationService(db_session)

        # Update using repository directly since update requires admin
        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        conversation = await service.update_conversation(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            name="Updated Group Name"
        )

        assert conversation is not None
        assert conversation["name"] == "Updated Group Name"

    async def test_update_conversation_not_admin_fails(
        self, db_session, test_user_2, test_conversation
    ):
        """Test updating conversation as non-admin fails."""
        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_conversation(
                conversation_id=test_conversation.id,
                user_id=test_user_2.id,
                name="New Name"
            )

        assert exc_info.value.status_code == 403
        assert "Only admins" in str(exc_info.value.detail)

    async def test_update_dm_conversation_fails(
        self, db_session, test_user, test_conversation, mocker
    ):
        """Test updating DM conversation fails."""
        # Convert to DM and make user admin
        test_conversation.type = ConversationType.DM
        await db_session.commit()

        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_conversation(
                conversation_id=test_conversation.id,
                user_id=test_user.id,
                name="New Name"
            )

        assert exc_info.value.status_code == 400
        assert "Cannot update DM" in str(exc_info.value.detail)

    async def test_add_members_success(
        self, db_session, test_user, test_conversation, mocker
    ):
        """Test adding members to conversation successfully."""
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
        mock_tms = mocker.patch("app.services.conversation_service.tms_client")
        mock_tms.get_users = mocker.AsyncMock(return_value=[{"tms_user_id": "test_user_789"}])

        service = ConversationService(db_session)

        result = await service.add_members(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            member_ids=[user3.id]
        )

        assert result["success"] is True
        assert result["affected_count"] == 1

    async def test_add_members_to_dm_fails(
        self, db_session, test_user, test_conversation
    ):
        """Test adding members to DM fails."""
        # Convert to DM
        test_conversation.type = ConversationType.DM
        await db_session.commit()

        service = ConversationService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.add_members(
                conversation_id=test_conversation.id,
                user_id=test_user.id,
                member_ids=[]
            )

        assert exc_info.value.status_code == 400
        assert "Cannot add members to DM" in str(exc_info.value.detail)

    async def test_remove_member_success(
        self, db_session, test_user, test_user_2, test_conversation
    ):
        """Test removing a member successfully."""
        # Make test_user admin
        from app.repositories.conversation_repo import ConversationMemberRepository
        member_repo = ConversationMemberRepository(db_session)
        await member_repo.update_role(
            test_conversation.id,
            test_user.id,
            ConversationRole.ADMIN
        )
        await db_session.commit()

        service = ConversationService(db_session)

        result = await service.remove_member(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            member_id=test_user_2.id
        )

        assert result["success"] is True
        assert result["affected_count"] == 1

    async def test_leave_conversation_success(
        self, db_session, test_user, test_conversation
    ):
        """Test leaving a conversation successfully."""
        service = ConversationService(db_session)

        result = await service.leave_conversation(
            conversation_id=test_conversation.id,
            user_id=test_user.id
        )

        assert result["success"] is True

    async def test_update_mute_settings_success(
        self, db_session, test_user, test_conversation
    ):
        """Test updating mute settings successfully."""
        service = ConversationService(db_session)

        result = await service.update_member_settings(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            is_muted=True
        )

        assert result["success"] is True
        assert result["is_muted"] is True

    async def test_mark_conversation_read_success(
        self, db_session, test_user, test_conversation
    ):
        """Test marking conversation as read successfully."""
        service = ConversationService(db_session)

        result = await service.mark_conversation_read(
            conversation_id=test_conversation.id,
            user_id=test_user.id
        )

        assert result["success"] is True
        assert "last_read_at" in result
        assert result["last_read_at"] is not None
