"""
Pytest configuration and fixtures for tests.
Provides reusable test fixtures for database, users, and data setup.
"""
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.models.base import Base
from app.config import settings


# Test database URL (use separate test database)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"  # In-memory SQLite for tests


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    TestSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def override_auth(test_user):
    """Override get_current_user dependency for tests."""
    async def mock_get_current_user():
        return {
            "tms_user_id": test_user.tms_user_id,
            "id": test_user.tms_user_id,
            "local_user_id": str(test_user.id),
            "email": "test@example.com",
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "name": "Test User",
            "display_name": "Test User",
            "role": "MEMBER",
            "is_active": True,
            "is_leader": False
        }
    return mock_get_current_user


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession, test_user, override_auth) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with dependency overrides."""
    from app.dependencies import get_current_user

    async def override_get_db():
        yield db_session

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def unauth_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client WITHOUT authentication (for testing unauthorized access)."""

    async def override_get_db():
        yield db_session

    # Only override database, not authentication
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    from app.models.user import User

    user = User(
        tms_user_id="test_user_123",
        settings_json={}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def test_user_2(db_session: AsyncSession):
    """Create a second test user."""
    from app.models.user import User

    user = User(
        tms_user_id="test_user_456",
        settings_json={}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def test_conversation(db_session: AsyncSession, test_user, test_user_2):
    """Create a test conversation with members."""
    from app.models.conversation import Conversation, ConversationMember, ConversationType

    # Create conversation
    conversation = Conversation(
        type=ConversationType.GROUP,
        name="Test Group",
        created_by=test_user.id
    )
    db_session.add(conversation)
    await db_session.flush()

    # Add members
    member1 = ConversationMember(
        conversation_id=conversation.id,
        user_id=test_user.id
    )
    member2 = ConversationMember(
        conversation_id=conversation.id,
        user_id=test_user_2.id
    )

    db_session.add(member1)
    db_session.add(member2)

    await db_session.commit()
    await db_session.refresh(conversation)

    return conversation


@pytest.fixture
async def test_message(db_session: AsyncSession, test_conversation, test_user):
    """Create a test message."""
    from app.models.message import Message, MessageType

    message = Message(
        conversation_id=test_conversation.id,
        sender_id=test_user.id,
        content="Test message content",
        type=MessageType.TEXT,
        metadata_json={}
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    return message


@pytest.fixture
def mock_tms_user_data():
    """Mock TMS user data."""
    return {
        "tms_user_id": "test_user_123",
        "username": "testuser",
        "email": "test@example.com",
        "role": "user",
        "avatar_url": "https://example.com/avatar.jpg"
    }


@pytest.fixture
def mock_auth_token():
    """Mock authentication token."""
    from app.core.security import create_access_token

    token = create_access_token(
        data={"tms_user_id": "test_user_123", "sub": "test_user_123"}
    )
    return token


@pytest.fixture
def auth_headers(mock_auth_token):
    """Create authentication headers."""
    return {"Authorization": f"Bearer {mock_auth_token}"}


@pytest.fixture(autouse=True)
def mock_websocket_manager(mocker):
    """Mock WebSocket connection manager for all tests."""
    mock_manager = mocker.AsyncMock()
    mock_manager.broadcast_new_message = mocker.AsyncMock()
    mock_manager.broadcast_message_edited = mocker.AsyncMock()
    mock_manager.broadcast_message_deleted = mocker.AsyncMock()
    mock_manager.broadcast_message_status = mocker.AsyncMock()
    mock_manager.broadcast_reaction_added = mocker.AsyncMock()
    mock_manager.broadcast_reaction_removed = mocker.AsyncMock()

    mocker.patch("app.core.websocket.connection_manager", mock_manager)
    mocker.patch("app.services.message_service.connection_manager", mock_manager)

    return mock_manager


@pytest.fixture(autouse=True)
def mock_tms_client(mocker):
    """Mock TMS client for all tests."""
    mock_client = mocker.AsyncMock()

    # Mock get_user method
    mock_client.get_user = mocker.AsyncMock(return_value={
        "id": "test_user_123",
        "email": "test@example.com",
        "username": "testuser",
        "firstName": "Test",
        "lastName": "User",
        "name": "Test User",
        "role": "MEMBER",
        "isActive": True,
        "isLeader": False,
        "image": None,
        "division": "Engineering",
        "department": "Development",
        "positionTitle": "Developer"
    })

    # Mock get_current_user_from_tms method
    mock_client.get_current_user_from_tms = mocker.AsyncMock(return_value={
        "id": "test_user_123",
        "email": "test@example.com",
        "username": "testuser",
        "firstName": "Test",
        "lastName": "User",
        "name": "Test User",
        "role": "MEMBER",
        "isActive": True,
        "isLeader": False
    })

    # Mock search_users method
    mock_client.search_users = mocker.AsyncMock(return_value={
        "users": []
    })

    # Mock health_check method
    mock_client.health_check = mocker.AsyncMock(return_value=True)

    # Patch all TMS client references
    mocker.patch("app.core.tms_client.tms_client", mock_client)
    mocker.patch("app.dependencies.tms_client", mock_client)
    mocker.patch("app.services.user_service.tms_client", mock_client)
    mocker.patch("app.services.message_service.tms_client", mock_client)

    return mock_client
