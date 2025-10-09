# GCG Team Messaging App - Server

**FastAPI backend for Viber-inspired team messaging application integrated with Team Management System (TMS)**

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database management
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **python-socketio** - WebSocket server
- **PyJWT** - JWT token validation
- **PostgreSQL** - Primary database
- **Alibaba Cloud Redis** - Caching & message queue

### Infrastructure
- **Alibaba Cloud** - Hosting platform
- **Alibaba Cloud OSS** - Media storage & optimization
- **GitHub Actions** - CI/CD pipeline

### Communication
- **WebSockets** - Real-time messaging
- **WebRTC Signaling** - Voice/video call signaling
- **HTTPS/TLS** - Encrypted communication

---

## 📁 Server Project Structure

```
tms-server/                            # Server repository root
├── alembic/                           # Database migrations
│   ├── versions/                      # Migration files
│   └── env.py
│
├── app/
│   ├── main.py                        # FastAPI app entry (~100 lines)
│   ├── config.py                      # Configuration (~150 lines)
│   ├── dependencies.py                # Dependency injection (~200 lines)
│   │
│   ├── api/                          # API routes (thin controllers)
│   │   └── v1/                       # API version 1
│   │       ├── __init__.py
│   │       ├── auth.py               # Auth endpoints (~200 lines)
│   │       ├── messages.py           # Message endpoints (~300 lines)
│   │       ├── conversations.py      # Conversation endpoints (~250 lines)
│   │       ├── users.py              # User endpoints (~200 lines)
│   │       ├── calls.py              # Call endpoints (~250 lines)
│   │       ├── polls.py              # Poll endpoints (~150 lines)
│   │       ├── files.py              # File upload endpoints (~200 lines)
│   │       └── deps.py               # Route dependencies (~150 lines)
│   │
│   ├── core/                         # Core functionality
│   │   ├── __init__.py
│   │   ├── security.py               # Auth/JWT utils (~300 lines)
│   │   ├── tms_client.py             # TMS API client (~400 lines)
│   │   ├── cache.py                  # Redis operations (~250 lines)
│   │   ├── websocket.py              # WebSocket manager (~500 lines)
│   │   └── config.py                 # Configuration models (~200 lines)
│   │
│   ├── services/                     # Business logic (keep < 500 lines!)
│   │   ├── __init__.py
│   │   ├── message_service.py        # Message logic (~450 lines)
│   │   ├── conversation_service.py   # Conversation logic (~400 lines)
│   │   ├── user_service.py           # User sync logic (~350 lines)
│   │   ├── call_service.py           # Call logic (~400 lines)
│   │   ├── poll_service.py           # Poll logic (~300 lines)
│   │   ├── notification_service.py   # Notification logic (~350 lines)
│   │   └── file_service.py           # File handling (~350 lines)
│   │
│   ├── repositories/                 # Database access (one per table)
│   │   ├── __init__.py
│   │   ├── base.py                   # Base repository (~200 lines)
│   │   ├── message_repo.py           # Message CRUD (~300 lines)
│   │   ├── conversation_repo.py      # Conversation CRUD (~250 lines)
│   │   ├── user_repo.py              # User CRUD (~200 lines)
│   │   ├── call_repo.py              # Call CRUD (~200 lines)
│   │   └── poll_repo.py              # Poll CRUD (~200 lines)
│   │
│   ├── models/                       # SQLAlchemy models (one per table)
│   │   ├── __init__.py
│   │   ├── base.py                   # Base model (~50 lines)
│   │   ├── user.py                   # User model (~100 lines)
│   │   ├── conversation.py           # Conversation model (~120 lines)
│   │   ├── message.py                # Message model (~150 lines)
│   │   ├── call.py                   # Call model (~100 lines)
│   │   ├── poll.py                   # Poll model (~120 lines)
│   │   └── user_block.py             # User block model (~80 lines)
│   │
│   ├── schemas/                      # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── message.py                # Message schemas (~200 lines)
│   │   ├── conversation.py           # Conversation schemas (~150 lines)
│   │   ├── user.py                   # User schemas (~100 lines)
│   │   ├── call.py                   # Call schemas (~100 lines)
│   │   └── poll.py                   # Poll schemas (~120 lines)
│   │
│   ├── utils/                        # Utility functions
│   │   ├── __init__.py
│   │   ├── datetime.py               # Date utilities (~100 lines)
│   │   ├── validators.py             # Custom validators (~150 lines)
│   │   ├── formatters.py             # Data formatters (~100 lines)
│   │   └── helpers.py                # General helpers (~200 lines)
│   │
│   └── tests/                        # Tests mirror app structure
│       ├── __init__.py
│       ├── conftest.py               # Pytest fixtures (~300 lines)
│       ├── api/
│       │   └── v1/
│       │       ├── test_messages.py  (~400 lines)
│       │       └── test_conversations.py (~350 lines)
│       ├── services/
│       │   ├── test_message_service.py (~500 lines)
│       │   └── test_conversation_service.py (~450 lines)
│       └── repositories/
│           └── test_message_repo.py  (~400 lines)
│
├── .env.example                      # Environment template
├── .gitignore
├── requirements.txt                  # Python dependencies
├── pytest.ini                        # Pytest configuration
├── alembic.ini                       # Alembic configuration
├── Dockerfile                        # Docker config (optional)
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- TMS API access (API URL and API Key)

### Initial Setup

```bash
# Clone repository
git clone <server-repo-url>
cd tms-server

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Unix/MacOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env  # or code .env

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

Server will be running at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## ⚙️ Environment Variables

Create `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tms_messaging
DATABASE_URL_SYNC=postgresql://user:password@localhost:5432/tms_messaging
REDIS_URL=redis://localhost:6379/0

# TMS Integration
TMS_API_URL=https://your-tms-domain.com/api
TMS_API_KEY=your-tms-api-key-here

# Security
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
ALLOWED_ORIGINS=http://localhost:3000

# Alibaba Cloud OSS
OSS_ACCESS_KEY_ID=your-oss-access-key-id
OSS_ACCESS_KEY_SECRET=your-oss-access-key-secret
OSS_BUCKET_NAME=your-bucket-name
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com

# Environment
ENVIRONMENT=development
DEBUG=true
```

**Note**: Never commit the `.env` file to version control. All sensitive credentials should be managed through environment variables or secure secret management systems.

---

## 🔗 TMS Integration

**Critical: This app relies on Team Management System (TMS) for user identity and authentication**

### Authentication & SSO
- **SSO/Token Validation** - Validate TMS JWT/session tokens on every request
- **Session Management** - Handle TMS session validation and expiry
- **Token Refresh** - Refresh expired TMS tokens automatically
- **Cross-Origin Authentication** - Handle authentication across TMS and TMA domains (CORS)
- **Logout Handling** - Sync logout with TMS

### User Data Integration
- **TMS API Integration** - Fetch user data from TMS (username, email, position, avatar, role)
- **User Data Caching** - Cache TMS user data in Redis (TTL: 5-15 minutes)
- **User Sync Service** - Periodic background sync of user data (every 10 minutes)
- **Real-time Updates** - TMS webhooks for instant user data updates (preferred)
- **Batch User Fetch** - Fetch multiple users efficiently (single API call)

### Authorization & Permissions
- **Role Mapping** - Map TMS roles to TMA permissions (admin, user, etc.)
- **Permission Validation** - Validate user permissions for actions
- **Group Admin Rights** - Determine admin rights based on TMS roles
- **Access Control** - Control feature access based on TMS permissions

### TMS Communication
- **TMS API Client** - Secure HTTP client for TMS communication (`app/core/tms_client.py`)
- **API Key Management** - Secure storage of TMS API credentials (environment variables)
- **Rate Limit Handling** - Handle TMS API rate limits gracefully
- **Error Handling** - Graceful handling of TMS API failures (fallback to cache)
- **Health Checks** - Monitor TMS API availability (ping endpoint)

---

## 🗄️ Database Architecture

### Core Tables Schema

```sql
-- User reference (TMS sync)
users (
  id UUID PRIMARY KEY,
  tms_user_id VARCHAR UNIQUE NOT NULL,
  settings_json JSONB DEFAULT '{}',
  last_synced_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
)

-- Conversations
conversations (
  id UUID PRIMARY KEY,
  type VARCHAR NOT NULL CHECK(type IN ('dm', 'group')),
  name VARCHAR,
  avatar_url VARCHAR,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
)

-- Conversation members
conversation_members (
  conversation_id UUID REFERENCES conversations(id),
  user_id UUID REFERENCES users(id),
  role VARCHAR DEFAULT 'member' CHECK(role IN ('admin', 'member')),
  joined_at TIMESTAMP DEFAULT NOW(),
  last_read_at TIMESTAMP,
  is_muted BOOLEAN DEFAULT FALSE,
  mute_until TIMESTAMP,
  PRIMARY KEY (conversation_id, user_id)
)

-- Messages
messages (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  sender_id UUID REFERENCES users(id),
  content TEXT,
  type VARCHAR NOT NULL CHECK(type IN ('text', 'image', 'file', 'voice', 'poll', 'call')),
  metadata_json JSONB DEFAULT '{}',
  reply_to_id UUID REFERENCES messages(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP,
  deleted_at TIMESTAMP,
  is_edited BOOLEAN DEFAULT FALSE
)

-- Message status (delivery/read receipts)
message_status (
  message_id UUID REFERENCES messages(id),
  user_id UUID REFERENCES users(id),
  status VARCHAR NOT NULL CHECK(status IN ('sent', 'delivered', 'read')),
  timestamp TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (message_id, user_id)
)

-- Message reactions
message_reactions (
  id UUID PRIMARY KEY,
  message_id UUID REFERENCES messages(id),
  user_id UUID REFERENCES users(id),
  emoji VARCHAR NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(message_id, user_id, emoji)
)

-- User blocks
user_blocks (
  blocker_id UUID REFERENCES users(id),
  blocked_id UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (blocker_id, blocked_id)
)

-- Calls
calls (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  type VARCHAR NOT NULL CHECK(type IN ('voice', 'video')),
  status VARCHAR NOT NULL CHECK(status IN ('completed', 'missed', 'declined', 'cancelled')),
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  created_by UUID REFERENCES users(id)
)

-- Call participants
call_participants (
  call_id UUID REFERENCES calls(id),
  user_id UUID REFERENCES users(id),
  joined_at TIMESTAMP,
  left_at TIMESTAMP,
  PRIMARY KEY (call_id, user_id)
)

-- Polls
polls (
  id UUID PRIMARY KEY,
  message_id UUID REFERENCES messages(id) UNIQUE,
  question TEXT NOT NULL,
  multiple_choice BOOLEAN DEFAULT FALSE,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
)

-- Poll options
poll_options (
  id UUID PRIMARY KEY,
  poll_id UUID REFERENCES polls(id),
  option_text VARCHAR NOT NULL,
  position INT NOT NULL
)

-- Poll votes
poll_votes (
  id UUID PRIMARY KEY,
  poll_id UUID REFERENCES polls(id),
  option_id UUID REFERENCES poll_options(id),
  user_id UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(poll_id, option_id, user_id)
)

-- Encryption keys (for E2EE - Phase 3)
encryption_keys (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  device_id VARCHAR NOT NULL,
  public_key TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, device_id)
)
```

### Database Indexes

```sql
CREATE INDEX idx_messages_conversation_created ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_conversation_members_user ON conversation_members(user_id);
CREATE INDEX idx_message_status_user ON message_status(user_id, status);
CREATE INDEX idx_user_blocks_blocker ON user_blocks(blocker_id);
CREATE INDEX idx_user_blocks_blocked ON user_blocks(blocked_id);
CREATE INDEX idx_users_tms_user_id ON users(tms_user_id);
CREATE INDEX idx_messages_reply_to ON messages(reply_to_id);
```

### Database Management
- **Database Migrations** - Alembic for version control
- **Database Transactions** - ACID compliance for data integrity
- **Connection Pooling** - Efficient database connection management

---

## 🔧 Core Infrastructure

### Caching & Queue System (Redis)
- **User Data Cache** - Cache TMS user data (TTL: 5-15 min, key: `user:{tms_user_id}`)
- **Session Cache** - Cache user sessions (TTL: 24 hours)
- **Presence Cache** - Cache online/offline status (TTL: 5 min, key: `presence:{user_id}`)
- **Offline Message Queue** - Queue messages for offline users (Redis List)
- **Cache Invalidation** - Smart cache invalidation on TMS webhooks
- **Cache Warming** - Preload frequently accessed data (active conversations)

### WebSocket Management
- **WebSocket Server** - python-socketio with FastAPI
- **Connection Pooling** - Efficient connection management (max 10,000 concurrent)
- **Heartbeat/Ping-Pong** - Keep-alive every 30 seconds
- **Auto-Reconnection** - Server-side connection state tracking
- **Connection State** - Track connection states (connected, disconnected, reconnecting)
- **Message Broadcasting** - Efficient message delivery to conversation members
- **Room Management** - WebSocket rooms per conversation
- **Namespace Isolation** - Separate namespaces for messaging, calls, notifications

### CORS Configuration

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI()

# CORS Middleware - configured via environment variables
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Set via ALLOWED_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🔒 Security

### API Security
- **Token Validation Middleware** - Validate TMS tokens on every request
- **Input Validation** - Validate all user inputs with Pydantic schemas
- **Input Sanitization** - Sanitize data to prevent injection attacks
- **SQL Injection Prevention** - Use SQLAlchemy ORM with parameterized queries
- **XSS Prevention** - Sanitize HTML/script content in messages
- **CSRF Protection** - CSRF tokens for state-changing operations
- **API Rate Limiting** - 100 requests/minute per user, 1000 requests/minute global
- **Request Size Limits** - Max 10MB per request

### Access Control
- **Permission-Based Access** - Role-based access control (RBAC)
- **Resource Authorization** - Verify user access to conversations/messages
- **Group Member Validation** - Verify group membership before allowing actions
- **Message Access Control** - Users can only access their conversation messages
- **File Access Control** - Secure file download URLs with signed tokens

### Network Security
- **CORS Configuration** - Whitelist TMS and TMA domains only
- **HTTPS Enforcement** - Force HTTPS for all connections
- **Secure Headers** - CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **IP Whitelisting** - Optional for admin endpoints
- **DDoS Protection** - Alibaba Cloud built-in + application-level rate limiting

### Data Security
- **Encryption at Rest** - Encrypt sensitive data in database (PostgreSQL pgcrypto)
- **Encryption in Transit** - TLS 1.3 for all communications
- **Secure File Storage** - Alibaba Cloud OSS with signed URLs
- **PII Protection** - Minimal PII storage (rely on TMS)

### Rate Limiting
- **Per-User Rate Limits** - 100 API calls/minute per tms_user_id
- **Per-Endpoint Limits** - Different limits for expensive endpoints
- **WebSocket Rate Limits** - Max 10 messages/second per user
- **File Upload Limits** - Max 5 uploads/minute per user, 10MB per file

---

## 📋 API Architecture

### Layered Architecture

```
API Routes → Services → Repositories → Models
(thin)      (fat)      (thin)         (data)
```

### API Design Principles

- **RESTful Standards** - Follow REST principles
- **API Versioning** - Version endpoints: `/api/v1/`
- **Consistent Responses** - Standard response format:
  ```json
  {
    "success": true,
    "data": {},
    "error": null
  }
  ```
- **Error Responses** - Consistent error format with error codes
- **Pagination** - Cursor-based pagination for lists
- **API Documentation** - Auto-generated docs via FastAPI (Swagger UI at `/docs`)

### File Size Guidelines

| File Type | Target Lines | Maximum Lines | Notes |
|-----------|--------------|---------------|-------|
| API Routes | 200-250 | 300 | Keep thin |
| Services | 300-400 | 500 | Business logic |
| Repositories | 200-250 | 300 | Database access |
| Models | 80-120 | 150 | One per table |
| Schemas | 100-150 | 200 | Pydantic models |
| Utilities | 150-250 | 300 | Group related |
| Test Files | 300-500 | 800 | Many test cases OK |

---

## 🧪 Testing

### Testing Strategy

- **Unit Tests** - Component and function unit tests
  - pytest with pytest-cov (target: 80% coverage)
  - Test services and repositories independently
- **Integration Tests** - API and service integration tests
  - Test TMS API integration
  - Test database operations
  - Test WebSocket events
- **Load Testing** - Performance and load testing (Phase 2)
  - Locust for simulating concurrent users

### Running Tests

```bash
# Run all tests
pytest

# Run specific directory
pytest tests/services/

# Verbose output
pytest -v

# With coverage
pytest --cov=app

# Run specific test file
pytest tests/api/v1/test_messages.py
```

### Code Quality

```bash
# Format code
black app/
isort app/

# Lint
flake8 app/
mypy app/

# All checks
black app/ && isort app/ && flake8 app/ && mypy app/
```

---

## 🚢 Deployment

### Deployment Steps

1. **Connect Repository** - Link GitHub repository to your hosting platform
2. **Configure Environment Variables** - Set all required env vars securely
3. **Database Setup** - Provision PostgreSQL and Redis instances
4. **Deploy** - Configure auto-deployment on push to main branch

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Environment variables configured securely
- [ ] Database migrations ready
- [ ] CORS origins set correctly
- [ ] TMS API credentials valid
- [ ] Alibaba Cloud OSS configured
- [ ] Health checks passing
- [ ] Security headers configured
- [ ] Rate limiting enabled

### Health Check Endpoints

- `/health` - Basic health check
- `/health/ready` - Ready check (includes DB and Redis)

---

## 🔍 Monitoring & Logging

### Monitoring
- **Error Tracking** - Sentry for error tracking and alerting
- **Performance Monitoring** - Track API response times (p50, p95, p99)
- **Database Query Monitoring** - Identify slow queries (log queries >100ms)
- **WebSocket Monitoring** - Track connection health and message latency

### Logging
- **Structured Logging** - JSON-formatted logs (timestamp, level, message, context)
- **Log Levels** - DEBUG (dev), INFO (prod), WARNING, ERROR, CRITICAL
- **Error Logging** - Log all errors to Sentry
- **Request Logging** - Log all API requests with response time

---

## 📝 Development Workflow

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add user table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Git Workflow

- **Feature Branches** - `feature/feature-name`
- **Bug Fixes** - `bugfix/bug-name`
- **Commit Conventions** - Conventional commits (feat, fix, docs, etc.)
- **Pull Requests** - All changes via PR with review

### Code Review Checklist

**Before submitting PR:**
- [ ] No file exceeds size limits
- [ ] Files follow naming conventions
- [ ] Single Responsibility Principle followed
- [ ] No code duplication (DRY)
- [ ] Proper error handling
- [ ] Type hints on all functions
- [ ] Unit tests for business logic
- [ ] Tests mirror source structure
- [ ] All tests pass
- [ ] Documentation updated if needed

---

## 📊 Performance Targets

### Response Times
- **API Response Time:** p95 < 200ms
- **WebSocket Latency:** < 100ms
- **Message Delivery:** < 500ms end-to-end
- **Database Queries:** < 100ms p95

### Reliability
- **Uptime:** 99.9% (< 43 minutes downtime/month)
- **Error Rate:** < 0.1%
- **WebSocket Reconnect:** < 5 seconds

### Scale
- **Concurrent Users:** 1,000+ (MVP), 10,000+ (Phase 2)
- **Messages/Second:** 100+ (MVP), 1,000+ (Phase 2)
- **Database Size:** Handle 1M+ messages
- **File Storage:** 100GB+ (Alibaba Cloud OSS)

---

## 🗺️ Implementation Phases

### Phase 1: MVP (Backend Focus)

#### Month 1: Foundation
- ✅ Setup project structure (FastAPI)
- ✅ Database schema and migrations
- ✅ TMS integration (auth, user sync)
- ✅ Redis caching setup

#### Month 2: Core Messaging
- ✅ Direct messaging endpoints (send, receive, history)
- ✅ Group chat endpoints (create, add/remove members)
- ✅ WebSocket real-time messaging
- ✅ Message status tracking (sent, delivered, read)
- ✅ Typing indicators
- ✅ File upload endpoints (images, documents)

#### Month 3: Enhanced Messaging
- ✅ Message reactions API
- ✅ Message replies API
- ✅ Message editing/deleting
- ✅ Voice message upload
- ✅ Link preview generation
- ✅ Search endpoints (messages, users, conversations)
- ✅ Notification service

#### Month 4: Calls & Polish
- ✅ WebRTC signaling server
- ✅ Call management endpoints
- ✅ Call history tracking
- ✅ User blocking endpoints
- ✅ Privacy settings API
- ✅ Bug fixes and optimization
- ✅ Testing and deployment

---

## 📚 Key Technical Decisions

### Why FastAPI?
- Modern, fast, type-safe
- Excellent WebSocket support
- Auto-generated API docs
- Async/await support
- Pydantic integration

### Why PostgreSQL?
- Reliable and mature
- Full-text search built-in
- JSON support (JSONB)
- Strong ACID guarantees
- Excellent with SQLAlchemy

### Why Redis?
- Fast caching layer
- Pub/sub for WebSocket broadcasting
- Message queue for offline users
- Session storage
- Rate limiting

### Simplified Decisions
- **No Microservices** - Start monolithic (simpler to develop and deploy)
- **PostgreSQL FTS** - No need for ElasticSearch initially
- **Simple Auth** - Rely on TMS (no custom auth needed)
- **No Custom Admin Panel (MVP)** - Use database tools initially

---

## 🆘 Troubleshooting

### Server won't start
- Check database connection (`DATABASE_URL` correct?)
- Check Redis connection (`REDIS_URL` correct?)
- Verify virtual environment is activated
- Check port 8000 is not in use: `lsof -i :8000` (Mac/Linux)

### Database issues
- Run migrations: `alembic upgrade head`
- Check PostgreSQL is running
- Verify database credentials
- Check database logs

### WebSocket connection fails
- Verify CORS settings include client origin
- Check WebSocket endpoint is accessible
- Review WebSocket logs for errors
- Test with WebSocket client tool

### TMS integration issues
- Verify TMS_API_URL is correct
- Check TMS_API_KEY is valid
- Test TMS API connectivity manually
- Review TMS API logs
- Check cache for stale data

---

## 📖 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [python-socketio Documentation](https://python-socketio.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)

---

## 📄 License

Proprietary - All Rights Reserved

---

## 👥 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

**Note:** This is the server-side repository for the TMS messaging application.
