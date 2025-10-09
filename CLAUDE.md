# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI backend for a Viber-inspired team messaging application. This server integrates with an external Team Management System (TMS) for user authentication and identity management. The app supports real-time messaging via WebSockets, file uploads, voice/video calls, and polls.

**Critical**: This backend does NOT manage its own user authentication. All user identity, authentication, and authorization comes from TMS via JWT token validation.

## Development Commands

### Initial Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Unix/MacOS
# venv\Scripts\activate   # On Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your actual credentials (never commit .env to git!)

# Run database migrations
alembic upgrade head
```

### Running the Server
```bash
# Development server with hot reload
uvicorn app.main:app --reload --port 8000

# Access API documentation at:
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app

# Run specific test file
pytest tests/api/v1/test_messages.py

# Run specific test directory
pytest tests/services/

# Verbose output
pytest -v

# Run specific test by name
pytest tests/services/test_message_service.py::test_send_message
```

### Code Quality & Formatting
```bash
# Format code (run before committing)
black app/
isort app/

# Type checking
mypy app/

# Linting
flake8 app/

# Run all checks together
black app/ && isort app/ && flake8 app/ && mypy app/
```

### Database Migrations
```bash
# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current migration version
alembic current
```

## Architecture Overview

### Layered Architecture Pattern
```
API Routes (thin)    →  Services (fat)    →  Repositories (thin)  →  Models (data)
  - Input validation     - Business logic     - Database queries      - SQLAlchemy models
  - Response formatting  - TMS integration    - CRUD operations       - Relationships
  - Dependency injection - Cache management   - Transaction handling  - Constraints
```

**Key Principle**: Keep API routes thin (200-300 lines). Business logic belongs in services (300-500 lines max). Repositories handle only database operations (200-300 lines).

### Project Structure
```
app/
├── main.py                    # FastAPI app entry, CORS, middleware
├── config.py                  # Configuration management
├── dependencies.py            # Dependency injection
│
├── api/v1/                    # API route handlers (thin controllers)
│   ├── auth.py               # Auth endpoints
│   ├── messages.py           # Message endpoints
│   ├── conversations.py      # Conversation endpoints
│   ├── users.py              # User endpoints
│   ├── calls.py              # Call endpoints
│   └── deps.py               # Route-level dependencies
│
├── core/                      # Core functionality
│   ├── security.py           # JWT validation, auth utilities
│   ├── tms_client.py         # TMS API client (user sync, validation)
│   ├── cache.py              # Redis operations
│   └── websocket.py          # WebSocket connection manager
│
├── services/                  # Business logic (< 500 lines each!)
│   ├── message_service.py    # Message sending, validation, threading
│   ├── conversation_service.py  # Conversation management
│   ├── user_service.py       # User sync from TMS
│   └── call_service.py       # Call signaling logic
│
├── repositories/              # Database access layer
│   ├── base.py               # Base repository with common CRUD
│   ├── message_repo.py       # Message queries
│   └── conversation_repo.py  # Conversation queries
│
├── models/                    # SQLAlchemy models (one per table)
│   ├── user.py               # User reference (synced from TMS)
│   ├── conversation.py       # Conversations (DM/group)
│   └── message.py            # Messages
│
├── schemas/                   # Pydantic request/response models
│   ├── message.py            # Message schemas
│   └── conversation.py       # Conversation schemas
│
└── utils/                     # Utility functions
    ├── datetime.py           # Date/time helpers
    └── validators.py         # Custom validators
```

### File Size Guidelines

| Component Type | Target Lines | Maximum Lines | Notes |
|---------------|--------------|---------------|-------|
| API Routes | 200-250 | 300 | Keep thin, delegate to services |
| Services | 300-400 | 500 | Business logic; split if exceeding |
| Repositories | 200-250 | 300 | Database access only |
| Models | 80-120 | 150 | One model per table |
| Schemas | 100-150 | 200 | Pydantic models |
| Tests | 300-500 | 800 | Many test cases OK |

**When a file approaches the maximum**: Split into smaller, focused modules or extract reusable utilities.

## TMS Integration Architecture

**Critical Concept**: This backend is a satellite to TMS. All user identity comes from TMS.

### Authentication Flow
1. Client sends request with TMS JWT token in `Authorization: Bearer <token>` header
2. Middleware validates token against TMS (via `app/core/security.py`)
3. Extract `tms_user_id` from validated token
4. Look up or create local `User` record (local reference only)
5. Proceed with request using local user record

### User Data Sync Pattern
```python
# app/services/user_service.py pattern:
async def get_user_data(tms_user_id: str):
    # 1. Check Redis cache first (key: f"user:{tms_user_id}")
    cached = await redis.get(f"user:{tms_user_id}")
    if cached:
        return json.loads(cached)

    # 2. Fetch from TMS API
    user_data = await tms_client.get_user(tms_user_id)

    # 3. Cache for 5-15 minutes
    await redis.setex(f"user:{tms_user_id}", 600, json.dumps(user_data))

    # 4. Update local reference (async background task)
    await user_repo.upsert_from_tms(tms_user_id, user_data)

    return user_data
```

### TMS Client Usage (`app/core/tms_client.py`)
```python
# Validate token
user_info = await tms_client.validate_token(jwt_token)

# Fetch user details
user = await tms_client.get_user(tms_user_id)

# Batch fetch users (for conversation participants)
users = await tms_client.get_users([id1, id2, id3])

# Handle errors gracefully - fallback to cache on TMS failure
```

## WebSocket Architecture

### WebSocket Manager Pattern (`app/core/websocket.py`)
- Uses python-socketio with FastAPI
- Maintains connection pool (max 10,000 concurrent)
- Heartbeat every 30 seconds
- Rooms per conversation: `conversation:{conversation_id}`
- Namespaces: `/messaging`, `/calls`, `/notifications`

### Common WebSocket Events
```python
# Client → Server
"join_conversation"     # Join conversation room
"send_message"          # Send message
"typing_start"          # User typing indicator
"typing_stop"           # Stop typing
"message_read"          # Mark message as read

# Server → Client
"new_message"           # New message received
"message_status"        # Message delivered/read
"user_typing"           # Someone is typing
"user_online"           # User came online
"user_offline"          # User went offline
```

## Database Patterns

### Key Tables
- `users`: Local reference to TMS users (stores `tms_user_id` + local settings)
- `conversations`: DMs and group chats
- `conversation_members`: User membership in conversations
- `messages`: All messages (text, images, files, voice)
- `message_status`: Delivery/read receipts per user
- `calls`: Voice/video call records
- `polls`: Polls with options and votes

### Important Indexes
```sql
-- Critical for performance
idx_messages_conversation_created ON messages(conversation_id, created_at DESC)
idx_conversation_members_user ON conversation_members(user_id)
idx_users_tms_user_id ON users(tms_user_id)
```

### Transaction Pattern
```python
# Use database sessions with automatic rollback
async with db.begin():
    # All operations in transaction
    message = await message_repo.create(data)
    await conversation_repo.update_timestamp(conversation_id)
    # Commits automatically; rolls back on exception
```

## Redis Caching Strategy

### Cache Keys and TTLs
```python
f"user:{tms_user_id}"              # TTL: 600s (10 min)
f"presence:{user_id}"              # TTL: 300s (5 min)
f"session:{session_id}"            # TTL: 86400s (24 hours)
f"conversation:{conv_id}:members"  # TTL: 900s (15 min)
```

### Cache Invalidation
- Invalidate on TMS webhooks (user updates)
- Invalidate on conversation membership changes
- Let presence cache expire naturally (short TTL)

## API Design Patterns

### Standard Response Format
```python
# Success response
{
    "success": true,
    "data": { ... },
    "error": null
}

# Error response
{
    "success": false,
    "data": null,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input",
        "details": { ... }
    }
}
```

### Pagination Pattern
```python
# Cursor-based pagination (for messages, conversations)
# Query params: ?cursor=<last_id>&limit=50

{
    "data": [...],
    "pagination": {
        "next_cursor": "uuid-here",
        "has_more": true,
        "total": 250  # optional
    }
}
```

### File Upload Pattern (Alibaba Cloud OSS)
1. Client requests signed upload URL: `POST /api/v1/files/upload-url`
2. Client uploads directly to Alibaba Cloud OSS using signed URL
3. Client sends file metadata to backend: `POST /api/v1/messages` with `oss_url`
4. Backend validates file type/size and stores message

**Alibaba Cloud OSS Integration**:
```python
# app/core/oss_client.py
import oss2
from app.config import settings

# Initialize OSS client
auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)

# Generate signed upload URL (valid for 1 hour)
def generate_upload_url(file_key: str) -> str:
    return bucket.sign_url('PUT', file_key, 3600)

# Generate signed download URL (valid for 1 hour)
def generate_download_url(file_key: str) -> str:
    return bucket.sign_url('GET', file_key, 3600)
```

## Security Checklist

### Every API Endpoint Must:
- [ ] Validate TMS JWT token via dependency injection
- [ ] Verify user has permission to access resource (conversation membership, etc.)
- [ ] Validate all inputs with Pydantic schemas
- [ ] Sanitize user-generated content (messages, names)
- [ ] Use parameterized queries (SQLAlchemy ORM handles this)
- [ ] Return appropriate error codes (400, 401, 403, 404, 500)

### Rate Limiting (implement in middleware)
- 100 API requests/minute per `tms_user_id`
- 10 messages/second per user (WebSocket)
- 5 file uploads/minute per user

## Common Development Patterns

### Creating a New Endpoint
1. Define Pydantic request/response schemas in `app/schemas/`
2. Create repository methods if new queries needed in `app/repositories/`
3. Implement business logic in service in `app/services/`
4. Create thin route handler in `app/api/v1/`
5. Add dependency for auth: `current_user: User = Depends(get_current_user)`
6. Write tests in `tests/` mirroring the source structure

### Adding a New Model
1. Create SQLAlchemy model in `app/models/`
2. Create repository in `app/repositories/` extending `BaseRepository`
3. Create migration: `alembic revision --autogenerate -m "Add model"`
4. Review and edit migration file (auto-generation isn't perfect)
5. Apply migration: `alembic upgrade head`

### Testing Pattern
```python
# tests/services/test_message_service.py
import pytest
from app.services.message_service import MessageService

@pytest.fixture
async def message_service(db_session, mock_tms_client):
    return MessageService(db_session, mock_tms_client)

async def test_send_message(message_service, test_user, test_conversation):
    message = await message_service.send_message(
        conversation_id=test_conversation.id,
        sender_id=test_user.id,
        content="Hello"
    )
    assert message.content == "Hello"
    assert message.sender_id == test_user.id
```

## Performance Considerations

### Response Time Targets
- API endpoints: p95 < 200ms
- WebSocket message delivery: < 100ms
- Database queries: p95 < 100ms

### Optimization Techniques
- Use `select_related()` / `joinedload()` for SQLAlchemy to avoid N+1 queries
- Paginate all list endpoints (cursor-based for messages)
- Cache expensive TMS API calls (user lookups)
- Use Redis pub/sub for WebSocket message broadcasting
- Index frequently queried fields (see database schema in README)

### Query Optimization Example
```python
# Bad: N+1 queries
messages = await message_repo.get_by_conversation(conv_id)
for msg in messages:
    sender = await user_repo.get(msg.sender_id)  # N queries!

# Good: Single query with join
messages = await message_repo.get_by_conversation_with_senders(conv_id)
# Uses joinedload(Message.sender)
```

## Error Handling

### Service Layer Pattern
```python
from fastapi import HTTPException

class MessageService:
    async def send_message(self, conversation_id, sender_id, content):
        # Verify membership
        is_member = await self.conversation_repo.is_member(conversation_id, sender_id)
        if not is_member:
            raise HTTPException(status_code=403, detail="Not a conversation member")

        # Verify not blocked
        # ... business logic ...

        try:
            message = await self.message_repo.create(data)
        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            raise HTTPException(status_code=500, detail="Failed to send message")

        return message
```

### TMS API Failure Handling
```python
try:
    user_data = await tms_client.get_user(tms_user_id)
except TMSAPIException:
    # Fallback to cache
    cached = await cache.get(f"user:{tms_user_id}")
    if cached:
        return cached
    # If no cache, raise to client
    raise HTTPException(status_code=503, detail="TMS unavailable")
```

## Environment Variables

Required variables (see `.env.example`):
- `DATABASE_URL`: Async PostgreSQL connection string (postgresql+asyncpg://...)
- `DATABASE_URL_SYNC`: Sync PostgreSQL connection string for Alembic
- `REDIS_URL`: Redis connection string (Alibaba Cloud Redis compatible)
- `TMS_API_URL`: Team Management System API base URL
- `TMS_API_KEY`: API key for authenticating with TMS
- `JWT_SECRET`: Secret for validating TMS JWT tokens (min 32 chars)
- `ALLOWED_ORIGINS`: CORS allowed origins (comma-separated)
- `OSS_ACCESS_KEY_ID`: Alibaba Cloud OSS Access Key ID
- `OSS_ACCESS_KEY_SECRET`: Alibaba Cloud OSS Access Key Secret
- `OSS_BUCKET_NAME`: OSS bucket name
- `OSS_ENDPOINT`: OSS endpoint (e.g., oss-cn-hangzhou.aliyuncs.com)
- `ENVIRONMENT`: `development`, `staging`, or `production`
- `DEBUG`: `true` or `false`

## Troubleshooting

### "Database connection failed"
- Check `DATABASE_URL` is correct in `.env`
- Ensure PostgreSQL is running: `pg_isready` (if installed locally)
- Run migrations: `alembic upgrade head`

### "TMS API authentication failed"
- Verify `TMS_API_KEY` is valid
- Check `TMS_API_URL` is correct and accessible
- Test TMS endpoint manually: `curl $TMS_API_URL/health`

### "WebSocket connection drops frequently"
- Check Redis is running (used for WebSocket state)
- Review WebSocket logs for errors
- Verify CORS settings include client origin
- Check heartbeat interval (default 30s)

### "Tests failing with database errors"
- Ensure test database is separate from development database
- Check `tests/conftest.py` for test database setup
- Run migrations on test database if needed

## Additional Notes

- The comprehensive project documentation is in `README.md`
- This project uses conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, etc.
- All PRs require tests and should not decrease code coverage
- Keep services under 500 lines - split if approaching limit
- Rely on TMS for user data - don't duplicate user management logic
- **Security**: Never commit `.env` files, credentials, or API keys to version control
- All sensitive configuration should be managed through environment variables
