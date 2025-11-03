# Key File Locations Reference

## Authentication Files

### Core Security & JWT Validation
- **JWT Validator (Local validation):** `/home/aiofficer/Workspace/tms-server/app/core/jwt_validator.py`
  - `decode_nextauth_jwt()` - Validates JWT locally (5ms)
  - `extract_user_id_from_token()` - Quick user ID extraction
  - `is_token_expired()` - Token expiration check

- **Security Utilities:** `/home/aiofficer/Workspace/tms-server/app/core/security.py`
  - `decode_nextauth_token()` - Strict token validation
  - `extract_token_from_header()` - Parse Bearer token
  - `create_access_token()` - Create JWT tokens
  - `verify_password()` / `hash_password()` - Password utilities

### GCGC User Management Client
- **TMS Client:** `/home/aiofficer/Workspace/tms-server/app/core/tms_client.py`
  - `TMSClient` class - Communicates with GCGC API
  - `get_user_by_id_with_api_key()` - Preferred method for user fetch
  - `get_user()` - Alternative user fetch with Bearer token
  - `get_users()` - Batch fetch with cache optimization
  - `get_current_user_from_tms()` - Fetch /users/me endpoint
  - `search_users()` - User search functionality
  - `health_check()` - GCGC availability check

### Dependency Injection
- **Dependencies:** `/home/aiofficer/Workspace/tms-server/app/dependencies.py`
  - `get_current_user()` - Main auth dependency (optimized)
  - `get_current_user_optional()` - Optional auth dependency
  - `get_admin_user()` - Admin-only check
  - `get_pagination_params()` - Pagination helper

### Caching
- **Redis Cache:** `/home/aiofficer/Workspace/tms-server/app/core/cache.py`
  - `RedisCache` class - Connection pooling
  - `cache_user_data()` - Cache user with TTL
  - `get_cached_user_data()` - Retrieve cached user
  - `invalidate_user_cache()` - Clear cache

---

## API Endpoints

### Authentication Endpoints
- **Auth Routes:** `/home/aiofficer/Workspace/tms-server/app/api/v1/auth.py`
  - `POST /api/v1/auth/login` - Validate token + sync user
  - `POST /api/v1/auth/validate` - Lightweight token check
  - `GET /api/v1/auth/me` - Alternative to /users/me
  - `POST /api/v1/auth/logout` - Placeholder logout
  - `GET /api/v1/auth/health` - Auth service health

### User Endpoints
- **User Routes:** `/home/aiofficer/Workspace/tms-server/app/api/v1/users.py`
  - `GET /api/v1/users/me` - Get current user
  - `GET /api/v1/users/{id}` - Get user by ID
  - `GET /api/v1/users?q=...` - Search users
  - `POST /api/v1/users/sync` - Manual sync (admin)
  - `DELETE /api/v1/users/cache/{id}` - Invalidate cache (admin)

---

## Data Models & Repositories

### User Model
- **User Model:** `/home/aiofficer/Workspace/tms-server/app/models/user.py`
  - Stores minimal local user reference
  - Key fields: `tms_user_id`, `email`, `username`, `role`, `division`, `department`
  - Tracks sync state: `last_synced_at`
  - Stores local settings: `settings_json`

### User Repository
- **User Repository:** `/home/aiofficer/Workspace/tms-server/app/repositories/user_repo.py`
  - `get_by_tms_user_id()` - Query by TMS ID
  - `upsert_from_tms()` - Insert/update from GCGC data
  - `batch_upsert_from_tms()` - Batch sync
  - `search_users()` - Full-text search
  - `get_active_users()` - Fetch active users
  - `get_users_needing_sync()` - Stale data detection

### User Service
- **User Service:** `/home/aiofficer/Workspace/tms-server/app/services/user_service.py`
  - Business logic for user operations
  - `get_current_user()` - Auth + sync flow
  - `sync_user_from_tms()` - Single user sync
  - `sync_users_batch()` - Batch sync
  - `sync_active_users()` - Sync stale users
  - `search_users()` - User search logic

### Schemas (Request/Response)
- **User Schemas:** `/home/aiofficer/Workspace/tms-server/app/schemas/user.py`
  - `UserResponse` - API response schema
  - `TMSCurrentUserSchema` - /users/me response from GCGC
  - `TMSPublicUserSchema` - /users/{id} response from GCGC
  - `TMSSearchUserSchema` - Search result from GCGC
  - `UserSearchRequest` - Search request schema
  - `UserSyncRequest` / `UserSyncResponse` - Sync operations

---

## Configuration & Setup

### Configuration
- **Settings:** `/home/aiofficer/Workspace/tms-server/app/config.py`
  - `Settings` class with validation
  - Environment variable loading
  - CORS origins parsing
  - JWT and NextAuth secrets
  - GCGC API configuration

### Application Entry Point
- **Main App:** `/home/aiofficer/Workspace/tms-server/app/main.py`
  - FastAPI app initialization
  - CORS middleware setup
  - Global exception handler
  - WebSocket integration
  - Health check endpoints

### Database
- **Database Setup:** `/home/aiofficer/Workspace/tms-server/app/core/database.py`
  - SQLAlchemy async configuration
  - AsyncSessionLocal
  - `get_db()` dependency

---

## Environment Configuration

### Required Environment Variables

```bash
# Authentication
JWT_SECRET=<min-32-chars>
NEXTAUTH_SECRET=<must-match-gcgc>

# GCGC User Management System
USER_MANAGEMENT_API_URL=<gcgc-api-url>
USER_MANAGEMENT_API_KEY=<api-key>
USER_MANAGEMENT_API_TIMEOUT=30

# Database
DATABASE_URL=postgresql://user:pass@host/db
DATABASE_URL_SYNC=postgresql://user:pass@host/db

# Redis (Optional)
REDIS_URL=redis://localhost:6379

# CORS
ALLOWED_ORIGINS=http://localhost:3000

# Caching TTLs
CACHE_USER_TTL=600
CACHE_PRESENCE_TTL=300
CACHE_SESSION_TTL=86400
```

---

## Performance Metrics Summary

| Operation | Time | File Location |
|-----------|------|----------------|
| JWT decode (local) | 5ms | `/app/core/jwt_validator.py` |
| Database lookup | 10-20ms | `/app/repositories/user_repo.py` |
| Redis cache hit | 2ms | `/app/core/cache.py` |
| GCGC API call | 200-500ms | `/app/core/tms_client.py` |
| User upsert | 5-15ms | `/app/repositories/user_repo.py` |
| **Total (cached)** | **15-25ms** | Dependencies in `/app/dependencies.py` |
| **Total (sync)** | **250-600ms** | `/app/dependencies.py` |

---

## Authentication Flow File Chain

### For a typical authenticated request:

1. Client sends: `Authorization: Bearer <JWT>`
2. FastAPI dependency: `/app/dependencies.py::get_current_user()`
3. Extract token: `/app/core/security.py::extract_token_from_header()`
4. Decode JWT: `/app/core/jwt_validator.py::decode_nextauth_jwt()`
5. Query DB: `/app/repositories/user_repo.py::get_by_tms_user_id()`
6. Check sync needed: `/app/dependencies.py` (24-hour logic)
7. Fetch if needed: `/app/core/tms_client.py::get_user_by_id_with_api_key()`
8. Upsert: `/app/repositories/user_repo.py::upsert_from_tms()`
9. Cache result: `/app/core/cache.py::cache_user_data()`
10. Return user dict: `/app/dependencies.py` (end of flow)

### For login endpoint:

1. Client sends: `POST /api/v1/auth/login { "token": "..." }`
2. Route handler: `/app/api/v1/auth.py::login()`
3. Decode token: `/app/core/security.py::decode_nextauth_token()`
4. Extract user ID from payload
5. Upsert to DB: `/app/repositories/user_repo.py::upsert_from_tms()`
6. Map to response: `/app/services/user_service.py::_map_user_to_response()`
7. Return: `LoginResponse` schema

---

## Testing Key Files

To test authentication, focus on these files:

1. **JWT Validation:** Test `/app/core/jwt_validator.py` with various token scenarios
2. **Token Extraction:** Test `/app/core/security.py::extract_token_from_header()`
3. **User Sync:** Test `/app/repositories/user_repo.py::upsert_from_tms()` with GCGC data
4. **Caching:** Test `/app/core/cache.py` with Redis
5. **Integration:** Test `/app/dependencies.py::get_current_user()` end-to-end

---

## Key Concepts Reference

### Authentication Model: Delegated (Satellite)
- TMS Server does NOT manage users
- All user identity comes from GCGC
- Local database stores minimal reference
- JWT tokens are validated locally (fast)
- User data is fetched from GCGC on demand

### Sync Strategy: Telegram/Messenger Pattern
- **New users:** Always sync on first login
- **Existing users (<24h):** Use cached data
- **Stale users (>24h):** Re-sync on next login
- **GCGC down:** Fallback to JWT or cached data

### Security Model
- All endpoints protected with `Depends(get_current_user)`
- Admin endpoints check role: `Depends(get_admin_user)`
- Token validation is local (no GCGC call)
- CORS configured for client origins
- Parameterized queries prevent SQL injection

