"""
Unit tests for MessageService.
Tests business logic and service layer operations.
"""
import pytest
from uuid import uuid4
from fastapi import HTTPException

from app.services.message_service import MessageService
from app.models.message import MessageType, MessageStatusType


@pytest.mark.asyncio
class TestMessageService:
    """Test cases for MessageService."""

    async def test_send_message_success(
        self,
        db_session,
        test_user,
        test_conversation
    ):
        """Test sending a message successfully."""
        service = MessageService(db_session)

        message = await service.send_message(
            sender_id=test_user.id,
            conversation_id=test_conversation.id,
            content="Hello, World!",
            message_type=MessageType.TEXT
        )

        assert message is not None
        assert message["content"] == "Hello, World!"
        assert message["type"] == MessageType.TEXT
        assert str(message["sender_id"]) == str(test_user.id)
        assert str(message["conversation_id"]) == str(test_conversation.id)

    async def test_send_message_not_member(
        self,
        db_session,
        test_user,
        test_conversation
    ):
        """Test sending a message when user is not a member."""
        from app.models.user import User

        # Create non-member user
        non_member = User(tms_user_id="non_member_789", settings_json={})
        db_session.add(non_member)
        await db_session.commit()

        service = MessageService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.send_message(
                sender_id=non_member.id,
                conversation_id=test_conversation.id,
                content="Unauthorized message",
                message_type=MessageType.TEXT
            )

        assert exc_info.value.status_code == 403

    async def test_send_reply_message(
        self,
        db_session,
        test_user,
        test_conversation,
        test_message
    ):
        """Test sending a reply to a message."""
        service = MessageService(db_session)

        reply = await service.send_message(
            sender_id=test_user.id,
            conversation_id=test_conversation.id,
            content="This is a reply",
            message_type=MessageType.TEXT,
            reply_to_id=test_message.id
        )

        assert reply is not None
        assert reply["content"] == "This is a reply"
        assert str(reply["reply_to_id"]) == str(test_message.id)

    async def test_get_message_success(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test getting a message successfully."""
        service = MessageService(db_session)

        message = await service.get_message(test_message.id, test_user.id)

        assert message is not None
        assert str(message["id"]) == str(test_message.id)
        assert message["content"] == test_message.content

    async def test_get_message_not_found(
        self,
        db_session,
        test_user
    ):
        """Test getting a non-existent message."""
        service = MessageService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_message(uuid4(), test_user.id)

        assert exc_info.value.status_code == 404

    async def test_edit_message_success(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test editing a message successfully."""
        service = MessageService(db_session)

        updated = await service.edit_message(
            message_id=test_message.id,
            user_id=test_user.id,
            new_content="Updated content"
        )

        assert updated is not None
        assert updated["content"] == "Updated content"
        assert updated["is_edited"] is True

    async def test_edit_message_not_owner(
        self,
        db_session,
        test_user_2,
        test_message
    ):
        """Test editing a message by non-owner."""
        service = MessageService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.edit_message(
                message_id=test_message.id,
                user_id=test_user_2.id,
                new_content="Unauthorized edit"
            )

        assert exc_info.value.status_code == 403

    async def test_delete_message_success(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test deleting a message successfully."""
        service = MessageService(db_session)

        result = await service.delete_message(test_message.id, test_user.id)

        assert result["success"] is True
        assert "deleted_at" in result

    async def test_delete_message_not_owner(
        self,
        db_session,
        test_user_2,
        test_message
    ):
        """Test deleting a message by non-owner."""
        service = MessageService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_message(test_message.id, test_user_2.id)

        assert exc_info.value.status_code == 403

    async def test_add_reaction_success(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test adding a reaction successfully."""
        service = MessageService(db_session)

        reaction = await service.add_reaction(
            message_id=test_message.id,
            user_id=test_user.id,
            emoji="👍"
        )

        assert reaction is not None
        assert reaction["emoji"] == "👍"
        assert str(reaction["user_id"]) == str(test_user.id)

    async def test_add_duplicate_reaction(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test adding a duplicate reaction."""
        service = MessageService(db_session)

        # Add first reaction
        await service.add_reaction(
            message_id=test_message.id,
            user_id=test_user.id,
            emoji="👍"
        )

        # Try to add same reaction again
        with pytest.raises(HTTPException) as exc_info:
            await service.add_reaction(
                message_id=test_message.id,
                user_id=test_user.id,
                emoji="👍"
            )

        assert exc_info.value.status_code == 409

    async def test_remove_reaction_success(
        self,
        db_session,
        test_user,
        test_message
    ):
        """Test removing a reaction successfully."""
        service = MessageService(db_session)

        # Add reaction first
        await service.add_reaction(
            message_id=test_message.id,
            user_id=test_user.id,
            emoji="👍"
        )

        # Remove reaction
        result = await service.remove_reaction(
            message_id=test_message.id,
            user_id=test_user.id,
            emoji="👍"
        )

        assert result["success"] is True

    async def test_mark_messages_read(
        self,
        db_session,
        test_user,
        test_conversation,
        test_message
    ):
        """Test marking messages as read."""
        service = MessageService(db_session)

        result = await service.mark_messages_read(
            message_ids=[test_message.id],
            user_id=test_user.id,
            conversation_id=test_conversation.id
        )

        assert result["success"] is True
        assert result["updated_count"] == 1

    async def test_get_conversation_messages(
        self,
        db_session,
        test_user,
        test_conversation
    ):
        """Test getting conversation messages with pagination."""
        service = MessageService(db_session)

        # Create multiple messages
        for i in range(5):
            from app.models.message import Message, MessageType

            msg = Message(
                conversation_id=test_conversation.id,
                sender_id=test_user.id,
                content=f"Message {i}",
                type=MessageType.TEXT,
                metadata_json={}
            )
            db_session.add(msg)

        await db_session.commit()

        # Get messages
        messages, next_cursor, has_more = await service.get_conversation_messages(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            limit=3
        )

        assert len(messages) == 3
        assert has_more is True
        assert next_cursor is not None

    async def test_search_messages(
        self,
        db_session,
        test_user,
        test_conversation
    ):
        """Test searching messages."""
        service = MessageService(db_session)

        # Create searchable messages
        from app.models.message import Message, MessageType

        msg1 = Message(
            conversation_id=test_conversation.id,
            sender_id=test_user.id,
            content="Python programming is great",
            type=MessageType.TEXT,
            metadata_json={}
        )
        msg2 = Message(
            conversation_id=test_conversation.id,
            sender_id=test_user.id,
            content="JavaScript is also cool",
            type=MessageType.TEXT,
            metadata_json={}
        )

        db_session.add_all([msg1, msg2])
        await db_session.commit()

        # Search for "Python"
        results = await service.search_messages(
            query="Python",
            user_id=test_user.id,
            conversation_id=test_conversation.id
        )

        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)
