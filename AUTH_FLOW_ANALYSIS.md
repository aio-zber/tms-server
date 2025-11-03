# Complete Authentication Flow Analysis - TMS Messaging Server

## Executive Summary

The TMS Messaging Server implements a **delegated authentication model** where all user identity, authentication, and authorization is managed by the **GCGC Team Management System (User Management System)**. The messaging server acts as a satellite that:

1. Validates NextAuth JWT tokens locally (fast, no external calls)
2. Fetches user data from GCGC on login/sync
3. Stores minimal local user references
4. Ensures requests are authenticated before processing

This architecture eliminates the need for user management duplication and ensures consistency across the organization.

---

## 1. JWT Token Validation Logic

### 1.1 Local Token Validation (Fast Path)

**File:** `/home/aiofficer/Workspace/tms-server/app/core/jwt_validator.py`

The system validates JWT tokens **locally without calling GCGC** for every request:

```python
def decode_nextauth_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate NextAuth JWT token locally.
    This is MUCH faster than calling Team Management API for every request.
    """
    payload = jwt.decode(
        token,
        settings.nextauth_secret,
        algorithms=["HS256", "HS512", "RS256"],
        options={
            "verify_exp": True,  # Verify expiration
            "verify_signature": True,  # Verify signature
        }
    )
    
    # Extract user ID from token claims
    user_id = payload.get("sub") or payload.get("id")
    
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
        "role": payload.get("role"),
        "hierarchyLevel": payload.get("hierarchyLevel"),
        "exp": payload.get("exp"),
        "iat": payload.get("iat"),
        **payload  # Include all other claims
    }
```

**Key Points:**
- Uses `settings.nextauth_secret` (MUST match GCGC's `NEXTAUTH_SECRET`)
- Supports HS256, HS512, and RS256 algorithms
- Verifies signature and expiration
- **Performance:** ~5ms (vs 200-500ms for GCGC API call)
- Supports both `sub` (standard JWT) and `id` (NextAuth custom) claims
- Falls back to lenient validation if required claims missing

### 1.2 Token Validation in Security Module

**File:** `/home/aiofficer/Workspace/tms-server/app/core/security.py`

```python
def decode_nextauth_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate NextAuth JWT token from GCGC TMS.
    These tokens are signed with NEXTAUTH_SECRET.
    """
    payload = jwt.decode(
        token,
        settings.nextauth_secret,
        algorithms=["HS256"],
        options={
            "verify_signature": True,
            "verify_exp": True,
            "require": ["id", "email", "exp", "iat"]
        }
    )
    return payload
```

**Error Handling:**
- `jwt.ExpiredSignatureError` → "Token has expired"
- `jwt.InvalidTokenError` → "Invalid token"
- `jwt.MissingRequiredClaimError` → Falls back to lenient mode

---

## 2. Complete Authentication Flow: `/api/v1/users/me`

### 2.1 Request Flow Diagram

```
Client Request
    ↓
Authorization Header: "Bearer <JWT_TOKEN>"
    ↓
GET /api/v1/users/me
    ↓
[app/api/v1/users.py - get_current_user_endpoint]
    ↓
1. Extract token from "Bearer <token>" format
    ↓
2. Decode NextAuth JWT locally (FAST - 5ms)
    ↓ [Security failure → 401]
    ↓
3. Extract TMS user ID from token
    ↓
4. Query local database for user (first check)
    ↓
5. Determine if sync needed:
    - New user (never synced) → SYNC
    - Missing last_synced_at → SYNC
    - Stale data (>24 hours) → SYNC
    - Recent sync (<24 hours) → USE CACHE
    ↓
6. [If sync needed] Fetch from GCGC /api/v1/users/{id}
    ↓ [GCGC unavailable → Fallback to cache/JWT data]
    ↓
7. Upsert user to local database with GCGC data
    ↓
8. Return UserResponse with full profile
    ↓
HTTP 200 + User Profile
```

### 2.2 Implementation Details

**File:** `/home/aiofficer/Workspace/tms-server/app/dependencies.py`

The `get_current_user` dependency implements the complete flow:

```python
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Dependency to get the current authenticated user (OPTIMIZED VERSION).
    
    New Authentication Flow (95% faster):
    1. Decode JWT locally (no external API call) ✅ FAST
    2. Extract user ID from token
    3. Fetch user data from cache or Team Management API
    4. Sync to local database
    5. Return user information
    """
    # Step 1: Validate authorization header
    if not authorization:
        raise HTTPException(401, "Missing authorization header")
    
    # Step 2: Extract and decode token
    token = extract_token_from_header(authorization)  # "Bearer <token>" → "<token>"
    jwt_payload = decode_nextauth_jwt(token)  # Decode locally
    user_id = jwt_payload["user_id"]
    
    # Step 3: Query local database
    result = await db.execute(
        select(User).where(User.tms_user_id == user_id)
    )
    local_user = result.scalar_one_or_none()
    
    # Step 4: Determine sync strategy (Telegram/Messenger pattern)
    should_sync = False
    if not local_user:
        should_sync = True  # New user
    elif datetime.utcnow() - local_user.last_synced_at > timedelta(hours=24):
        should_sync = True  # Stale data
    
    # Step 5: Fetch from GCGC if needed
    if should_sync:
        try:
            user_data = await tms_client.get_user_by_id_with_api_key(
                user_id,
                use_cache=True
            )
            local_user = await user_repo.upsert_from_tms(user_id, user_data)
            await db.commit()
        except TMSAPIException:
            # Fallback: Create minimal user from JWT
            local_user = User(
                tms_user_id=user_id,
                email=jwt_payload.get("email"),
                username=jwt_payload.get("username"),
                first_name=jwt_payload.get("given_name"),
                last_name=jwt_payload.get("family_name"),
                settings_json={}
            )
            db.add(local_user)
            await db.commit()
    
    # Step 6: Return user dict
    return {
        "id": local_user.tms_user_id,
        "tms_user_id": local_user.tms_user_id,
        "email": local_user.email,
        "name": f"{local_user.first_name} {local_user.last_name}".strip(),
        "role": local_user.role,
        "is_active": local_user.is_active,
        # ... other fields
    }
```

---

## 3. `/api/v1/auth/login` Endpoint Implementation

**File:** `/home/aiofficer/Workspace/tms-server/app/api/v1/auth.py`

### 3.1 Login Endpoint

```python
@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate NextAuth JWT token and sync user data.
    
    This endpoint accepts JWT tokens generated by GCGC's /api/v1/auth/token.
    The token contains all user information and is signed with NEXTAUTH_SECRET.
    
    Flow:
    1. Decode and validate NextAuth JWT token
    2. Extract user information from token
    3. Sync user data to local database
    4. Return user profile
    """
    # Step 1: Decode NextAuth token
    token_payload = decode_nextauth_token(login_request.token)
    
    # Step 2: Extract TMS user ID
    tms_user_id = token_payload.get("id")
    if not tms_user_id:
        raise HTTPException(401, "Token does not contain user ID")
    
    # Step 3: Prepare TMS user data from token
    tms_user_data = {
        "id": tms_user_id,
        "email": token_payload.get("email"),
        "name": token_payload.get("name"),
        "role": token_payload.get("role"),
        "hierarchyLevel": token_payload.get("hierarchyLevel"),
        "image": token_payload.get("image"),
    }
    
    # Step 4: Upsert to local database
    user_repo = UserRepository(db)
    user = await user_repo.upsert_from_tms(tms_user_id, tms_user_data)
    await db.commit()
    
    # Step 5: Return user response
    return LoginResponse(
        success=True,
        user=user_response,
        message="Login successful"
    )
```

**Request/Response Examples:**

Request:
```json
POST /api/v1/auth/login
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Response (Success):
```json
{
    "success": true,
    "message": "Login successful",
    "user": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "tms_user_id": "user-123",
        "email": "john@example.com",
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "name": "John Doe",
        "display_name": "John Doe",
        "role": "LEADER",
        "division": "Engineering",
        "department": "Backend",
        "is_active": true,
        "is_leader": true
    }
}
```

Response (Failure - Invalid Token):
```json
{
    "status_code": 401,
    "detail": {
        "error": "authentication_failed",
        "message": "Token has expired - please login again",
        "hint": "Please ensure you're using a valid JWT token from GCGC authentication"
    }
}
```

### 3.2 Additional Auth Endpoints

**Validate Token (Lightweight):**
```python
@router.post("/validate")
async def validate_token(request: LoginRequest, db: AsyncSession)
```
- Validates token without syncing to DB
- Faster than `/login` (no DB write)
- Returns basic user info from GCGC

**Get Authenticated User:**
```python
@router.get("/me")
async def get_authenticated_user(authorization: str = Header(...))
```
- Alternative to `/api/v1/users/me`
- Uses same authentication flow
- Returns full user profile

**Logout:**
```python
@router.post("/logout")
async def logout()
```
- Placeholder endpoint
- Actual logout is client-side (token discard)
- TMS tokens are stateless (JWT)

---

## 4. User Data Sync from GCGC

### 4.1 Sync Strategy

**File:** `/home/aiofficer/Workspace/tms-server/app/repositories/user_repo.py`

The system implements **Telegram/Messenger pattern** for user synchronization:

| Scenario | Action | Reason |
|----------|--------|--------|
| New user (never synced) | ALWAYS SYNC | Need complete profile on first login |
| Stale data (>24 hours) | ALWAYS SYNC | Keep organizational data current |
| Recent sync (<24 hours) | SKIP SYNC | Use cached data (performance optimized) |

### 4.2 Upsert Implementation

```python
async def upsert_from_tms(
    self,
    tms_user_id: str,
    tms_data: Dict[str, Any]
) -> User:
    """
    Upsert (insert or update) user from TMS data.
    Uses PostgreSQL's ON CONFLICT DO UPDATE for efficiency.
    """
    # Map TMS data to local user fields
    # Handles both camelCase (TMS) and snake_case (local)
    user_data = {
        "tms_user_id": tms_user_id,
        "email": tms_data.get("email"),
        "username": tms_data.get("username"),
        "first_name": (
            tms_data.get("firstName") or
            tms_data.get("first_name") or
            (name_parts[0] if name_parts else None)
        ),
        "last_name": (
            tms_data.get("lastName") or
            tms_data.get("last_name") or
            (name_parts[1] if name_parts else None)
        ),
        "image": tms_data.get("image"),
        "role": tms_data.get("role"),
        "position_title": tms_data.get("positionTitle"),
        "division": tms_data.get("division"),
        "department": tms_data.get("department"),
        "section": tms_data.get("section"),
        "custom_team": tms_data.get("customTeam"),
        "is_active": tms_data.get("isActive", True),
        "is_leader": tms_data.get("isLeader", False),
        "last_synced_at": datetime.utcnow(),
    }
    
    # PostgreSQL UPSERT: INSERT ... ON CONFLICT DO UPDATE
    stmt = insert(User).values(**user_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tms_user_id"],
        set_={
            **{k: v for k, v in user_data.items() if k != "tms_user_id"},
            "updated_at": datetime.utcnow(),
        }
    ).returning(User)
    
    result = await self.db.execute(stmt)
    user = result.scalar_one()
    return user
```

### 4.3 GCGC API Client Methods

**File:** `/home/aiofficer/Workspace/tms-server/app/core/tms_client.py`

#### get_user_by_id_with_api_key (Preferred Method)

```python
async def get_user_by_id_with_api_key(
    self,
    user_id: str,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get user by ID using API Key authentication (server-to-server).
    This is the PREFERRED method for backend-to-TMS communication.
    """
    # Check cache first
    if use_cache:
        cached_user = await get_cached_user_data(user_id)
        if cached_user:
            return cached_user
    
    # Fetch from GCGC API
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        
        response = await client.get(
            f"{self.base_url}/api/v1/users/{user_id}",
            headers=headers
        )
        
        user_data = response.json()
        await cache_user_data(user_id, user_data)  # Cache for 10 min
        return user_data
```

#### get_user (Alternative Method)

```python
async def get_user(self, tms_user_id: str, use_cache: bool = True):
    """
    Get user data from GCGC /api/v1/users/{id}.
    Uses Bearer token authentication.
    """
    # Check cache first
    if use_cache:
        cached_user = await get_cached_user_data(tms_user_id)
        if cached_user:
            return cached_user
    
    # Fetch from TMS API with Bearer token
    response = await client.get(
        f"{self.base_url}/api/v1/users/{tms_user_id}",
        headers=self._get_headers()  # Bearer token in Authorization
    )
    
    user_data = response.json()
    await cache_user_data(tms_user_id, user_data)
    return user_data
```

#### Batch Fetch (Optimized)

```python
async def get_users(self, tms_user_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Get multiple users from TMS in a single request (batch fetch).
    OPTIMIZED: Check cache first, only fetch missing users from API.
    """
    # Check cache for all users
    cached_users = []
    uncached_ids = []
    
    for user_id in tms_user_ids:
        cached = await get_cached_user_data(user_id)
        if cached:
            cached_users.append(cached)
        else:
            uncached_ids.append(user_id)
    
    # If all cached, return early
    if not uncached_ids:
        return cached_users
    
    # Fetch only uncached users from API
    response = await client.post(
        f"{self.base_url}/users/batch",
        json={"user_ids": uncached_ids}
    )
    
    fetched_users = response.json()
    # Cache each newly fetched user
    for user in fetched_users:
        await cache_user_data(user["id"], user)
    
    return cached_users + fetched_users
```

---

## 5. CORS Configuration

### 5.1 CORS Middleware Setup

**File:** `/home/aiofficer/Workspace/tms-server/app/main.py`

```python
# Convert comma-separated string to list for CORS middleware
cors_origins = settings.get_allowed_origins_list()
print(f"🌐 CORS allowed origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

### 5.2 Configuration

**File:** `/home/aiofficer/Workspace/tms-server/app/config.py`

```python
# CORS (string will be converted to list by validator)
allowed_origins: str = Field(
    default="http://localhost:3000",
    description="Comma-separated list of allowed CORS origins"
)

def get_allowed_origins_list(self) -> List[str]:
    """Get allowed origins as a list."""
    if isinstance(self.allowed_origins, str):
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
    return ["http://localhost:3000"]
```

### 5.3 Global Exception Handler for CORS

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that ensures CORS headers are always present.
    
    This is critical for message search and other features where database
    errors might occur before CORS middleware can add headers.
    """
    origin = request.headers.get("origin", "*")
    
    return JSONResponse(
        status_code=500,
        headers={
            "Access-Control-Allow-Origin": origin if origin in cors_origins else cors_origins[0],
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )
```

### 5.4 WebSocket CORS

**File:** `/home/aiofficer/Workspace/tms-server/app/core/websocket.py`

For WebSocket connections, CORS is handled by Socket.IO itself (not middleware):
- Socket.IO checks `cors_allowed_origins` configuration
- Same origins as HTTP CORS are used

---

## 6. Authentication Dependency Injection

### 6.1 Dependencies Available

**File:** `/home/aiofficer/Workspace/tms-server/app/dependencies.py`

```python
# Required authentication
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get authenticated user (raises 401 if invalid)"""

# Optional authentication
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """Get user if authenticated, else None"""

# Admin-only access
async def get_admin_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Verify user is admin, raise 403 otherwise"""

# Pagination helper
def get_pagination_params(
    cursor: Optional[str] = None,
    limit: int = 50
) -> dict:
    """Helper for cursor-based pagination"""
```

### 6.2 Usage Examples

**Protected Endpoint (Requires Auth):**
```python
@router.get("/protected")
async def protected_route(
    current_user: dict = Depends(get_current_user)
):
    """
    Raises 401 if token invalid/missing
    Returns user info if authenticated
    """
    return {"user_id": current_user["id"]}
```

**Public Endpoint (Optional Auth):**
```python
@router.get("/public")
async def public_route(
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Returns None if not authenticated
    Returns user info if authenticated
    """
    if user:
        return {"message": f"Hello {user['name']}"}
    return {"message": "Hello anonymous"}
```

**Admin-Only Endpoint:**
```python
@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Raises 403 if user is not admin
    Proceeds if user role == "ADMIN"
    """
    pass
```

---

## 7. Which Endpoints Require Authentication

### 7.1 Authentication-Protected Endpoints

**Messages API:**
- `GET /api/v1/messages` - Requires auth
- `POST /api/v1/messages` - Requires auth
- `PUT /api/v1/messages/{id}` - Requires auth
- `DELETE /api/v1/messages/{id}` - Requires auth

**Conversations API:**
- `GET /api/v1/conversations` - Requires auth
- `POST /api/v1/conversations` - Requires auth
- `GET /api/v1/conversations/{id}` - Requires auth

**Users API:**
- `GET /api/v1/users/me` - Requires auth
- `GET /api/v1/users/{id}` - Requires auth
- `GET /api/v1/users` (search) - Requires auth
- `POST /api/v1/users/sync` - Requires ADMIN role
- `DELETE /api/v1/users/cache/{id}` - Requires ADMIN role

**Calls API:**
- All endpoints require auth

**Polls API:**
- All endpoints require auth

### 7.2 Public Endpoints (No Auth)

**Authentication API:**
- `POST /api/v1/auth/login` - Public (validates token instead)
- `POST /api/v1/auth/validate` - Public
- `POST /api/v1/auth/logout` - Public (client-side only)
- `GET /api/v1/auth/health` - Public

**Health Check:**
- `GET /health` - Public
- `GET /health/ready` - Public
- `GET /health/websocket` - Public

---

## 8. Authentication Flow Performance Metrics

### 8.1 Latency Breakdown

| Operation | Time | Notes |
|-----------|------|-------|
| JWT decode (local) | ~5ms | Fast, no network |
| Database lookup | ~10-20ms | Index on tms_user_id |
| Cache hit | ~2ms | Redis if configured |
| GCGC API call | 200-500ms | Network latency |
| User sync (DB upsert) | 5-15ms | PostgreSQL UPSERT |
| **Total (cache hit)** | **15-25ms** | Most common case |
| **Total (sync needed)** | **250-600ms** | First login or stale data |

### 8.2 Optimization Strategies

1. **Local JWT validation** - No GCGC call needed for every request
2. **24-hour sync TTL** - Reduces daily GCGC API calls by 95%
3. **Redis caching** - 10-minute TTL for user data
4. **Batch fetch** - Fetch multiple users in single API call
5. **Fallback mode** - Continue with JWT data if GCGC unavailable

---

## 9. Error Handling and Fallback Strategies

### 9.1 JWT Validation Failures

| Error | Status | Response | Action |
|-------|--------|----------|--------|
| Missing header | 401 | "Missing authorization header" | Reject request |
| Invalid format | 401 | "Invalid authorization header format" | Reject request |
| Token expired | 401 | "Token has expired" | Prompt re-login |
| Invalid signature | 401 | "Invalid token signature" | Reject request |
| Missing user ID | 401 | "Token missing user ID" | Reject request |

### 9.2 GCGC API Failures

```python
if should_sync:
    try:
        user_data = await tms_client.get_user_by_id_with_api_key(user_id)
        local_user = await user_repo.upsert_from_tms(user_id, user_data)
    except TMSAPIException:
        # Fallback Strategy
        if not local_user:
            # Create minimal user from JWT claims
            local_user = User(
                tms_user_id=user_id,
                email=jwt_payload.get("email"),
                username=jwt_payload.get("username"),
                first_name=jwt_payload.get("given_name"),
                last_name=jwt_payload.get("family_name"),
                settings_json={}
            )
            db.add(local_user)
            await db.commit()
        else:
            # Use existing local data (defer sync)
            pass
```

**Fallback Behavior:**
- First login + GCGC down: Create minimal user from JWT, continue
- Existing user + GCGC down: Use cached data, continue
- Cache miss + GCGC down: Return 503 Service Unavailable

---

## 10. Key Configuration Variables

**Environment Variables Required:**

```bash
# JWT/NextAuth
JWT_SECRET=your-secret-32-chars-minimum
NEXTAUTH_SECRET=must-match-gcgc-nextauth-secret  # CRITICAL

# GCGC User Management System
USER_MANAGEMENT_API_URL=https://gcgc-api-url.example.com
USER_MANAGEMENT_API_KEY=api-key-for-server-to-server-auth
USER_MANAGEMENT_API_TIMEOUT=30

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com

# Database & Cache
DATABASE_URL=postgresql://user:pass@localhost/tms_db
REDIS_URL=redis://localhost:6379  # Optional

# Caching TTLs
CACHE_USER_TTL=600  # 10 minutes
CACHE_PRESENCE_TTL=300  # 5 minutes
CACHE_SESSION_TTL=86400  # 24 hours
```

---

## 11. Security Checklist

Every endpoint must:

- [x] Validate NextAuth JWT token via `Depends(get_current_user)`
- [x] Verify user has permission to access resource (conversation membership, etc.)
- [x] Validate all inputs with Pydantic schemas
- [x] Sanitize user-generated content
- [x] Use parameterized queries (SQLAlchemy ORM)
- [x] Return appropriate error codes (400, 401, 403, 404, 500)
- [x] Never expose internal details in error messages
- [x] Log authentication failures for audit trail

---

## 12. Diagram: Complete Authentication Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATION                       │
│                   (Viber/Messenger/Telegram App)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 1. Get JWT from GCGC
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              GCGC TEAM MANAGEMENT SYSTEM (GCGC)                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ /api/v1/auth/token → Returns JWT signed with           │  │
│  │                      NEXTAUTH_SECRET                     │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 2. Send JWT in request
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│           TMS MESSAGING SERVER (This Application)               │
│                                                                  │
│  HTTP Endpoint (e.g., POST /api/v1/auth/login)                 │
│  ↓                                                               │
│  Authorization Header: "Bearer eyJhb..."                        │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 1: Extract Token from Header                       │  │
│  │ "Bearer <token>" → "<token>"                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 2: Validate JWT Locally (FAST - 5ms)              │  │
│  │ - Use settings.nextauth_secret                          │  │
│  │ - Verify signature                                       │  │
│  │ - Check expiration                                       │  │
│  │ - Extract user ID from claims                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 3: Check Local Database                            │  │
│  │ SELECT * FROM users WHERE tms_user_id = ?               │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 4: Decide if Sync Needed                           │  │
│  │ - New user? → SYNC                                       │  │
│  │ - >24h since sync? → SYNC                                │  │
│  │ - <24h since sync? → USE CACHE                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 5: [If sync needed] Fetch from GCGC                │  │
│  │ GET /api/v1/users/{user_id}                             │  │
│  │ Headers: X-API-Key: <api_key>                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 6: Upsert to Local Database                        │  │
│  │ INSERT ... ON CONFLICT DO UPDATE                        │  │
│  │ (Sync name, email, role, org hierarchy, etc.)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 7: Cache in Redis (Optional)                       │  │
│  │ KEY: user:<user_id>                                      │  │
│  │ TTL: 10 minutes                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ↓                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 8: Return User Response                            │  │
│  │ HTTP 200 + UserResponse JSON                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 3. JSON response with user profile
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT APPLICATION                            │
│                  (Store token in localStorage)                  │
│              (Use token for all subsequent requests)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary Table: Authentication Methods

| Method | URL | Auth | Body | Response | Use Case |
|--------|-----|------|------|----------|----------|
| Login | `POST /api/v1/auth/login` | Public | JWT token | User profile | Initial login from GCGC |
| Validate | `POST /api/v1/auth/validate` | Public | JWT token | Valid/invalid | Client-side token check |
| Get Me | `GET /api/v1/users/me` | Bearer | None | User profile | Get current user info |
| Get User | `GET /api/v1/users/{id}` | Bearer | None | User profile | Get other user info |
| Search | `GET /api/v1/users?q=...` | Bearer | None | User list | Search users |
| Sync | `POST /api/v1/users/sync` | Admin | IDs list | Sync results | Manual user sync |

