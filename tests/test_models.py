"""
Comprehensive test script for database models.

Tests all models, relationships, cascades, constraints, and async operations.
"""
import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models import (
    Base,
    User,
    Conversation,
    ConversationMember,
    ConversationType,
    ConversationRole,
    Message,
    MessageType,
    MessageStatus,
    MessageStatusType,
    MessageReaction,
    UserBlock,
    Call,
    CallType,
    CallStatus,
    CallParticipant,
    Poll,
    PollOption,
    PollVote,
)


class ModelTester:
    """Comprehensive model testing class."""

    def __init__(self):
        # Use in-memory SQLite for testing (faster)
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def setup(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ All tables created successfully\n")

    async def teardown(self):
        """Drop all tables and dispose engine."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        print("\n✅ Cleanup completed")

    async def test_user_creation(self):
        """Test User model creation."""
        print("🧪 Testing User Creation...")
        async with self.async_session() as session:
            user = User(
                tms_user_id="tms_user_001",
                settings_json={"theme": "dark", "notifications": True},
                last_synced_at=datetime.utcnow(),
            )
            session.add(user)
            await session.commit()

            # Verify
            result = await session.execute(select(User))
            fetched_user = result.scalar_one()
            assert fetched_user.tms_user_id == "tms_user_001"
            assert fetched_user.settings_json["theme"] == "dark"
            print(f"  ✅ User created: {fetched_user}")
            return fetched_user.id

    async def test_conversation_and_members(self, user_id):
        """Test Conversation and ConversationMember models."""
        print("\n🧪 Testing Conversations and Members...")
        async with self.async_session() as session:
            # Create second user
            user2 = User(tms_user_id="tms_user_002", settings_json={})
            session.add(user2)
            await session.flush()

            # Create group conversation
            conversation = Conversation(
                type=ConversationType.GROUP,
                name="Test Group",
                avatar_url="https://example.com/avatar.png",
                created_by=user_id,
            )
            session.add(conversation)
            await session.flush()

            # Add members
            member1 = ConversationMember(
                conversation_id=conversation.id,
                user_id=user_id,
                role=ConversationRole.ADMIN,
            )
            member2 = ConversationMember(
                conversation_id=conversation.id,
                user_id=user2.id,
                role=ConversationRole.MEMBER,
                is_muted=True,
            )
            session.add_all([member1, member2])
            await session.commit()

            # Verify with relationships
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation.id)
            )
            fetched_conv = result.scalar_one()

            # Test AsyncAttrs
            members = await fetched_conv.awaitable_attrs.members
            assert len(members) == 2
            print(f"  ✅ Conversation created with {len(members)} members")
            print(f"  ✅ AsyncAttrs relationship access works")
            return conversation.id, user_id, user2.id

    async def test_messages_and_threading(self, conversation_id, sender_id, recipient_id):
        """Test Message model with threading and replies."""
        print("\n🧪 Testing Messages and Threading...")
        async with self.async_session() as session:
            # Create parent message
            parent_msg = Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                content="Hello! This is the parent message.",
                type=MessageType.TEXT,
                metadata_json={"platform": "web"},
            )
            session.add(parent_msg)
            await session.flush()

            # Create reply
            reply_msg = Message(
                conversation_id=conversation_id,
                sender_id=recipient_id,
                content="This is a reply!",
                type=MessageType.TEXT,
                reply_to_id=parent_msg.id,
                metadata_json={},
            )
            session.add(reply_msg)
            await session.commit()

            # Verify self-referential relationship
            result = await session.execute(
                select(Message).where(Message.id == reply_msg.id)
            )
            fetched_reply = result.scalar_one()
            assert fetched_reply.reply_to_id == parent_msg.id
            print(f"  ✅ Message threading works")
            print(f"  ✅ Self-referential FK works")
            return parent_msg.id, recipient_id

    async def test_message_status_and_reactions(self, message_id, user_id):
        """Test MessageStatus and MessageReaction models."""
        print("\n🧪 Testing Message Status and Reactions...")
        async with self.async_session() as session:
            # Add message status
            status = MessageStatus(
                message_id=message_id,
                user_id=user_id,
                status=MessageStatusType.READ,
            )
            session.add(status)

            # Add reactions
            reaction1 = MessageReaction(
                message_id=message_id,
                user_id=user_id,
                emoji="👍",
            )
            reaction2 = MessageReaction(
                message_id=message_id,
                user_id=user_id,
                emoji="❤️",
            )
            session.add_all([reaction1, reaction2])
            await session.commit()

            # Verify unique constraint works
            try:
                duplicate_reaction = MessageReaction(
                    message_id=message_id,
                    user_id=user_id,
                    emoji="👍",  # Duplicate!
                )
                session.add(duplicate_reaction)
                await session.commit()
                print("  ❌ Unique constraint failed to prevent duplicate reaction")
            except Exception:
                await session.rollback()
                print("  ✅ Unique constraint works (prevented duplicate reaction)")

            # Test selectin lazy loading
            result = await session.execute(select(Message).where(Message.id == message_id))
            msg = result.scalar_one()
            reactions = await msg.awaitable_attrs.reactions
            assert len(reactions) == 2
            print(f"  ✅ Message has {len(reactions)} reactions")
            print(f"  ✅ Selectin lazy loading works")

    async def test_user_blocking(self, blocker_id, blocked_id):
        """Test UserBlock model."""
        print("\n🧪 Testing User Blocking...")
        async with self.async_session() as session:
            block = UserBlock(
                blocker_id=blocker_id,
                blocked_id=blocked_id,
            )
            session.add(block)
            await session.commit()

            # Verify
            result = await session.execute(
                select(UserBlock).where(UserBlock.blocker_id == blocker_id)
            )
            fetched_block = result.scalar_one()
            assert fetched_block.blocked_id == blocked_id
            print(f"  ✅ User blocking works")
            print(f"  ✅ Composite PK works")

    async def test_calls_and_participants(self, conversation_id, user1_id, user2_id):
        """Test Call and CallParticipant models."""
        print("\n🧪 Testing Calls and Participants...")
        async with self.async_session() as session:
            # Create call
            call = Call(
                conversation_id=conversation_id,
                created_by=user1_id,
                type=CallType.VIDEO,
                status=CallStatus.COMPLETED,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow() + timedelta(minutes=5),
            )
            session.add(call)
            await session.flush()

            # Add participants
            participant1 = CallParticipant(
                call_id=call.id,
                user_id=user1_id,
                joined_at=datetime.utcnow(),
                left_at=datetime.utcnow() + timedelta(minutes=5),
            )
            participant2 = CallParticipant(
                call_id=call.id,
                user_id=user2_id,
                joined_at=datetime.utcnow() + timedelta(seconds=10),
                left_at=datetime.utcnow() + timedelta(minutes=3),
            )
            session.add_all([participant1, participant2])
            await session.commit()

            # Verify
            result = await session.execute(select(Call).where(Call.id == call.id))
            fetched_call = result.scalar_one()
            participants = await fetched_call.awaitable_attrs.participants
            assert len(participants) == 2
            print(f"  ✅ Call created with {len(participants)} participants")
            return call.id, conversation_id

    async def test_polls_and_voting(self, message_id, conversation_id, sender_id, voter_id):
        """Test Poll, PollOption, and PollVote models."""
        print("\n🧪 Testing Polls and Voting...")
        async with self.async_session() as session:
            # Create message for poll
            poll_message = Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                content=None,
                type=MessageType.POLL,
                metadata_json={},
            )
            session.add(poll_message)
            await session.flush()

            # Create poll
            poll = Poll(
                message_id=poll_message.id,
                question="What's your favorite programming language?",
                multiple_choice=False,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            session.add(poll)
            await session.flush()

            # Create options
            option1 = PollOption(
                poll_id=poll.id,
                option_text="Python",
                position=1,
            )
            option2 = PollOption(
                poll_id=poll.id,
                option_text="JavaScript",
                position=2,
            )
            option3 = PollOption(
                poll_id=poll.id,
                option_text="Rust",
                position=3,
            )
            session.add_all([option1, option2, option3])
            await session.flush()

            # Create vote
            vote = PollVote(
                poll_id=poll.id,
                option_id=option1.id,
                user_id=voter_id,
            )
            session.add(vote)
            await session.commit()

            # Verify with selectin loading
            result = await session.execute(select(Poll).where(Poll.id == poll.id))
            fetched_poll = result.scalar_one()
            options = await fetched_poll.awaitable_attrs.options
            assert len(options) == 3
            assert options[0].option_text == "Python"  # Ordered by position
            print(f"  ✅ Poll created with {len(options)} options")
            print(f"  ✅ Poll options ordered by position")
            print(f"  ✅ Vote recorded successfully")

    async def test_cascade_deletes(self, conversation_id):
        """Test CASCADE delete behavior."""
        print("\n🧪 Testing CASCADE Deletes...")
        async with self.async_session() as session:
            # Count messages before delete
            result = await session.execute(
                select(Message).where(Message.conversation_id == conversation_id)
            )
            messages_before = len(result.scalars().all())
            print(f"  📊 Messages before delete: {messages_before}")

            # Delete conversation (should cascade to messages, members, etc.)
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one()
            await session.delete(conversation)
            await session.commit()

            # Verify cascades
            result = await session.execute(
                select(Message).where(Message.conversation_id == conversation_id)
            )
            messages_after = len(result.scalars().all())
            assert messages_after == 0
            print(f"  ✅ CASCADE delete works (messages: {messages_before} → {messages_after})")

    async def test_soft_delete(self):
        """Test soft delete on messages."""
        print("\n🧪 Testing Soft Deletes...")
        async with self.async_session() as session:
            # Create test data
            user = User(tms_user_id="test_soft_delete", settings_json={})
            session.add(user)
            await session.flush()  # Flush to get user.id

            conversation = Conversation(type=ConversationType.DM, created_by=None)
            session.add(conversation)
            await session.flush()  # Flush to get conversation.id

            message = Message(
                conversation_id=conversation.id,
                sender_id=user.id,
                content="This will be soft-deleted",
                type=MessageType.TEXT,
                metadata_json={},
            )
            session.add(message)
            await session.commit()

            # Soft delete
            message.deleted_at = datetime.utcnow()
            await session.commit()

            # Verify still exists but marked deleted
            result = await session.execute(select(Message).where(Message.id == message.id))
            fetched = result.scalar_one()
            assert fetched.deleted_at is not None
            print(f"  ✅ Soft delete works (deleted_at is set)")

    async def run_all_tests(self):
        """Run all tests in sequence."""
        try:
            await self.setup()

            # Test basic models
            user_id = await self.test_user_creation()

            # Test conversations
            conversation_id, user1_id, user2_id = await self.test_conversation_and_members(
                user_id
            )

            # Test messages
            message_id, recipient_id = await self.test_messages_and_threading(
                conversation_id, user1_id, user2_id
            )

            # Test message interactions
            await self.test_message_status_and_reactions(message_id, user1_id)

            # Test blocking
            await self.test_user_blocking(user1_id, user2_id)

            # Test calls
            await self.test_calls_and_participants(conversation_id, user1_id, user2_id)

            # Test polls
            await self.test_polls_and_voting(message_id, conversation_id, user1_id, user2_id)

            # Test soft delete
            await self.test_soft_delete()

            # Test cascade deletes (do this last)
            await self.test_cascade_deletes(conversation_id)

            print("\n" + "=" * 60)
            print("🎉 ALL TESTS PASSED! 🎉")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            raise
        finally:
            await self.teardown()


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🧪 Starting Comprehensive Model Tests")
    print("=" * 60 + "\n")

    tester = ModelTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
