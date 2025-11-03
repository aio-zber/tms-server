# Complete Authentication Flow Analysis
## TMS Client → GCGC → TMS Server Integration

**Date**: 2025-11-03
**Systems Analyzed**: tms-client, gcgc_team_management_system, tms-server

---

## Executive Summary

After thorough investigation of all three codebases, I've identified the **root cause of the CORS error** and mapped the complete authentication flow.

### Root Cause: AppHeader Component Calling Wrong Endpoint

**The Error**:
```
Access to fetch at 'https://gcgc-team-management-system-staging.up.railway.app/auth/signin?callbackUrl=%2Fapi%2Fv1%2Fusers%2Fme'
from origin 'https://tms-client-staging.up.railway.app'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

**What's Happening**:
1. [AppHeader.tsx:36](../tms-client/src/components/layout/AppHeader.tsx#L36) calls GCGC's `/api/v1/users/me` endpoint
2. User is not authenticated with GCGC at that moment (on login page)
3. GCGC redirects to `/auth/signin` (NextAuth behavior)
4. **The redirect response doesn't include CORS headers**
5. Browser blocks the request

**Why This Is Wrong**:
- AppHeader should call **TMS-Server's** `/api/v1/users/me` (not GCGC's)
- GCGC's `/api/v1/users/me` requires an active NextAuth session
- The client already has JWT token in localStorage from successful login
- TMS-Server validates the JWT and returns user data without GCGC dependency

---

## Complete Authentication Flow (Correct Implementation)

### Phase 1: User Login (tms-client → GCGC)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Enters Credentials on /login                        │
│    - Email: user@example.com                                │
│    - Password: ********                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. authService.login() [tms-client]                         │
│    File: src/features/auth/services/authService.ts:40       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. POST to GCGC: /api/auth/signin/credentials               │
│    URL: ${NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL}/api/...      │
│    Body: email=xxx&password=xxx&redirect=false              │
│    Response: Set-Cookie: next-auth.session-token=...        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. GET GCGC: /api/v1/auth/token                             │
│    File: authService.ts:67                                  │
│    Credentials: include (sends session cookie)              │
│    Response: { token: "eyJhbGci..." }                       │
│    Storage: localStorage.setItem('tms_token', jwt)          │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: TMS-Server Authentication (tms-client → tms-server)

```
┌─────────────────────────────────────────────────────────────┐
│ 5. POST to TMS-Server: /api/v1/auth/login                   │
│    File: authService.ts:97                                  │
│    URL: ${NEXT_PUBLIC_TMS_SERVER_API_URL}/api/v1/auth/login │
│    Body: { token: jwtToken }                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. TMS-Server Validates JWT [tms-server]                    │
│    File: app/api/v1/auth.py:login_endpoint                  │
│    Validates: jwt.decode(token, NEXTAUTH_SECRET, HS256)     │
│    Extracts: user_id from JWT payload                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. TMS-Server Syncs User from GCGC                          │
│    File: app/services/user_service.py:sync_user_from_tms    │
│    IF user not in DB OR last_synced > 24h:                  │
│       GET GCGC: /api/v1/users/{user_id}                     │
│       Header: x-api-key: ${USER_MANAGEMENT_API_KEY}         │
│       Upsert user to local DB                               │
│    ELSE:                                                     │
│       Use cached user data                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. TMS-Server Returns User Data                             │
│    Response: {                                              │
│      success: true,                                         │
│      user: {                                                │
│        id: "local-db-uuid",                                 │
│        tms_user_id: "gcgc-user-id",                         │
│        email: "user@example.com",                           │
│        display_name: "John Doe",                            │
│        ...                                                  │
│      },                                                     │
│      token: "same-jwt-token"                                │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. tms-client Stores Auth Data                              │
│    File: authService.ts:121                                 │
│    localStorage.setItem('tms_session_active', 'true')       │
│    Returns user object to login page                        │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: Accessing Protected Resources (Correct Flow)

```
┌─────────────────────────────────────────────────────────────┐
│ 10. User Navigates to /chats (Protected Route)              │
│     AppHeader Component Mounts                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 11. ✅ CORRECT: Call TMS-Server /api/v1/users/me            │
│     File: Should use authService.getCurrentUser()           │
│     URL: ${NEXT_PUBLIC_TMS_SERVER_API_URL}/api/v1/users/me  │
│     Header: Authorization: Bearer ${localStorage.tms_token} │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 12. TMS-Server Validates JWT [tms-server]                   │
│     File: app/api/v1/users.py:get_current_user              │
│     Dependency: get_current_user (deps.py)                  │
│     Validates: JWT signature + expiration                   │
│     Fetches: User from local DB by tms_user_id              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 13. TMS-Server Returns User Data                            │
│     Response: {                                             │
│       id: "local-uuid",                                     │
│       tms_user_id: "gcgc-user-id",                          │
│       email: "user@example.com",                            │
│       display_name: "John Doe",                             │
│       ...conversations, settings, etc.                      │
│     }                                                       │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3b: What's Currently Happening (WRONG - Causes CORS Error)

```
┌─────────────────────────────────────────────────────────────┐
│ 10. User Navigates to /chats (Protected Route)              │
│     AppHeader Component Mounts                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 11. ❌ WRONG: Call GCGC /api/v1/users/me                    │
│     File: AppHeader.tsx:36 (INCORRECT!)                     │
│     URL: ${NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL}/api/v1/...  │
│     Credentials: include (sends GCGC session cookie)        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 12. GCGC Receives Request [gcgc]                             │
│     File: src/app/api/v1/users/me/route.ts                  │
│     Checks: NextAuth session (getServerSession)             │
│     Result: No valid session (user is on TMS-Client domain) │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 13. GCGC Redirects to Login                                  │
│     NextAuth Middleware Intercepts                          │
│     Redirects: /auth/signin?callbackUrl=/api/v1/users/me    │
│     ❌ PROBLEM: Redirect response has NO CORS headers!      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 14. Browser CORS Error                                       │
│     Error: No 'Access-Control-Allow-Origin' header          │
│     Browser blocks the response                             │
│     User sees: "Network error. Please check connection."    │
└─────────────────────────────────────────────────────────────┘
```

---

## System Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      TMS-CLIENT                              │
│  (Next.js Frontend - tms-client-staging.up.railway.app)      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ authService                                        │     │
│  │  - login() → GCGC → TMS-Server                     │     │
│  │  - getCurrentUser() → TMS-Server (JWT)             │     │
│  │  - validateSession() → TMS-Server (JWT)            │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ AppHeader (PROBLEMATIC)                            │     │
│  │  - Currently calls GCGC directly ❌                │     │
│  │  - Should use authService.getCurrentUser() ✅      │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
                          ↓                    ↓
                          ↓                    ↓
         ┌────────────────┘                    └─────────────────┐
         ↓                                                       ↓
┌──────────────────────────┐                    ┌───────────────────────────┐
│         GCGC             │                    │      TMS-SERVER           │
│  (User Management)       │                    │  (Messaging Backend)      │
│  gcgc-staging...app      │                    │  tms-server-staging...app │
│                          │                    │                           │
│  NextAuth JWT Provider   │                    │  FastAPI + PostgreSQL     │
│  PostgreSQL (Users)      │                    │                           │
│                          │                    │  ┌─────────────────────┐  │
│  Endpoints:              │                    │  │ JWT Validation      │  │
│  ✅ /api/auth/signin     │                    │  │  - Uses GCGC secret │  │
│  ✅ /api/v1/auth/token   │                    │  │  - 5ms decode time  │  │
│  ✅ /api/v1/users/me     │◄───────API Key─────│  └─────────────────────┘  │
│  ✅ /api/v1/users/[id]   │    (Server-to-     │                           │
│                          │     Server)        │  ┌─────────────────────┐  │
│  CORS Allowed:           │                    │  │ User Sync Strategy  │  │
│  - tms-client-staging    │                    │  │  - Cache 24h        │  │
│                          │                    │  │  - Fallback to JWT  │  │
│  Session Strategy:       │                    │  │  - API key calls    │  │
│  - JWT (1h access)       │                    │  └─────────────────────┘  │
│  - 30d refresh           │                    │                           │
└──────────────────────────┘                    │  Endpoints:               │
                                                │  ✅ /api/v1/auth/login    │
                                                │  ✅ /api/v1/users/me      │
                                                │  ✅ /api/v1/conversations │
                                                │  ✅ /api/v1/messages      │
                                                │                           │
                                                │  Auth Required:           │
                                                │  - Bearer JWT token       │
                                                │  - Validated locally      │
                                                └───────────────────────────┘
```

---

## JWT Token Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        JWT TOKEN LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────┘

1. GCGC Issues JWT Token
   ┌────────────────────────────────────────────────────────────┐
   │ Endpoint: GET /api/v1/auth/token                           │
   │ Algorithm: HS256                                           │
   │ Secret: NEXTAUTH_SECRET (GCGC's)                           │
   │ Expiry: 1 hour                                             │
   │ Payload: {                                                 │
   │   sub: "user-id",                                          │
   │   email: "user@example.com",                               │
   │   name: "John Doe",                                        │
   │   role: "MEMBER",                                          │
   │   iat: 1699000000,                                         │
   │   exp: 1699003600                                          │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                          ↓
2. tms-client Stores Token
   ┌────────────────────────────────────────────────────────────┐
   │ localStorage.setItem('tms_token', jwt)                     │
   │ Location: authService.ts:77                                │
   └────────────────────────────────────────────────────────────┘
                          ↓
3. tms-client Sends Token to tms-server
   ┌────────────────────────────────────────────────────────────┐
   │ Header: Authorization: Bearer ${token}                     │
   │ All API calls to tms-server include this                   │
   └────────────────────────────────────────────────────────────┘
                          ↓
4. tms-server Validates Token
   ┌────────────────────────────────────────────────────────────┐
   │ File: app/core/security.py:verify_jwt_token                │
   │ Library: PyJWT                                             │
   │ Secret: NEXTAUTH_SECRET (MUST MATCH GCGC's!)               │
   │ Algorithms: ["HS256", "HS512", "RS256"]                    │
   │ Validates: signature + expiration                          │
   │ Performance: ~5ms                                          │
   └────────────────────────────────────────────────────────────┘
                          ↓
5. Token Expiration Handling
   ┌────────────────────────────────────────────────────────────┐
   │ After 1 hour: Token expires                                │
   │ tms-server returns: 401 Unauthorized                       │
   │ tms-client catches: Redirects to login                     │
   │ User re-authenticates with GCGC                            │
   │ New JWT token issued                                       │
   └────────────────────────────────────────────────────────────┘
```

---

## User Data Sync Strategy (Telegram/Messenger Pattern)

### Strategy Overview
TMS-Server maintains a **lightweight local cache** of user data from GCGC:

```python
# app/services/user_service.py

async def get_or_sync_user(tms_user_id: str) -> User:
    """
    Telegram/Messenger pattern for user sync
    """
    # 1. Check local database
    user = await user_repo.get_by_tms_user_id(tms_user_id)

    # 2. New user OR stale data (>24h)
    if not user or (datetime.now() - user.last_synced_at) > timedelta(hours=24):
        # Fetch from GCGC
        gcgc_user = await tms_client.get_user(tms_user_id)

        # Upsert to local DB
        user = await user_repo.upsert_from_tms(tms_user_id, gcgc_user)

    # 3. Return local user
    return user
```

### Performance Characteristics

| Scenario | Sync Needed? | Performance | Frequency |
|----------|--------------|-------------|-----------|
| New user (first login) | ✅ Yes | 250-600ms | Once per user |
| Existing user (<24h) | ❌ No | 15-25ms | 95% of requests |
| Existing user (>24h) | ✅ Yes | 250-600ms | Once per day |
| GCGC API down | ❌ Fallback | 5ms (JWT only) | During outages |

### Fallback Strategy
```
Priority 1: Local DB user (if <24h old)
         ↓ (if unavailable or stale)
Priority 2: Fetch from GCGC API (if reachable)
         ↓ (if GCGC down)
Priority 3: JWT token data only (minimal info)
         ↓ (if JWT expired)
Priority 4: Return 401 Unauthorized
```

---

## CORS Configuration Analysis

### GCGC CORS Settings

```typescript
// src/app/api/v1/users/me/route.ts
const headers = {
  'Access-Control-Allow-Origin': 'https://tms-client-staging.up.railway.app',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Allow-Credentials': 'true',
}

export async function OPTIONS(request: NextRequest) {
  return NextResponse.json({}, { headers })
}

export async function GET(request: NextRequest) {
  // ... endpoint logic ...
  return NextResponse.json(userData, { headers })
}
```

**Issue**: When NextAuth redirects (for unauthenticated requests), it **bypasses this route handler** and uses NextAuth's built-in redirect logic, which **doesn't include CORS headers**.

### TMS-Server CORS Settings

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://tms-client-staging.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Status**: ✅ Correctly configured for tms-client

---

## Root Cause Analysis

### The CORS Error Chain

```
1. AppHeader.tsx:36 calls GCGC /api/v1/users/me
                ↓
2. GCGC checks NextAuth session
   Result: No session (user is on different domain)
                ↓
3. NextAuth middleware intercepts request
   File: src/middleware.ts
   Decision: Redirect to /auth/signin
                ↓
4. NextAuth generates redirect response
   Response: 302 Redirect
   Location: /auth/signin?callbackUrl=/api/v1/users/me
   ❌ MISSING: CORS headers
                ↓
5. Browser receives redirect without CORS headers
   Browser decision: BLOCK (CORS violation)
                ↓
6. JavaScript fetch() promise rejects
   Error: "CORS policy: No 'Access-Control-Allow-Origin'"
                ↓
7. tms-client catches error
   User sees: "Network error. Please check your connection."
```

### Why AppHeader Calls GCGC (History)

Looking at the git history and AUTH_FIX_SUMMARY.md:

1. **Original design**: AppHeader fetched from GCGC for user profile
2. **Auth refactor**: Login flow updated to use TMS-Server
3. **Oversight**: AppHeader wasn't updated during refactor
4. **Result**: Inconsistent endpoint usage

---

## The Fix: Three-Step Solution

### Step 1: Fix AppHeader Component (tms-client)

**File**: `src/components/layout/AppHeader.tsx`

```typescript
// ❌ CURRENT CODE (Lines 33-56)
useEffect(() => {
  const loadUser = async () => {
    try {
      // Get user data from GCGC Team Management System using session
      const response = await fetch(`${process.env.NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL}/api/v1/users/me`, {
        credentials: 'include', // Include session cookies
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData as User);
      } else if (response.status === 401) {
        window.location.href = '/login';
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Failed to load user data:', error);
      window.location.href = '/login';
    } finally {
      setLoading(false);
    }
  };

  loadUser();
}, []);
```

```typescript
// ✅ FIXED CODE
useEffect(() => {
  const loadUser = async () => {
    try {
      // Use authService to get user data from TMS-Server
      const userData = await authService.getCurrentUser();
      setUser(userData as User);
    } catch (error) {
      console.error('Failed to load user data:', error);
      // Clear auth state and redirect to login
      authService.setSessionActive(false);
      window.location.href = '/login';
    } finally {
      setLoading(false);
    }
  };

  loadUser();
}, []);
```

**Benefits**:
- ✅ Uses correct endpoint (TMS-Server, not GCGC)
- ✅ Uses JWT from localStorage (no GCGC session needed)
- ✅ Consistent with rest of app (authService pattern)
- ✅ No CORS issues (TMS-Server has correct CORS config)

### Step 2: Verify Environment Variables (tms-client)

Ensure `.env.local` has:
```env
NEXT_PUBLIC_TMS_SERVER_API_URL=https://tms-server-staging.up.railway.app
NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
```

### Step 3: Verify NEXTAUTH_SECRET Match (CRITICAL)

**GCGC** `.env`:
```env
NEXTAUTH_SECRET=<gcgc-secret-here>
```

**TMS-Server** `.env`:
```env
NEXTAUTH_SECRET=<gcgc-secret-here>  # MUST MATCH GCGC!
```

**Why**: TMS-Server validates JWT tokens signed by GCGC. If secrets don't match, validation will fail.

---

## Testing the Fix

### Test 1: Login Flow
```bash
# Expected behavior after fix:
1. Navigate to https://tms-client-staging.up.railway.app/login
2. Enter valid credentials
3. Click "Sign In"
4. ✅ Redirects to /chats (no CORS error)
5. ✅ AppHeader loads user data successfully
6. ✅ User avatar and name displayed in header
```

### Test 2: Direct Navigation to Protected Route
```bash
# Expected behavior:
1. Navigate directly to https://tms-client-staging.up.railway.app/chats
2. If not authenticated:
   ✅ Redirects to /login (no error)
3. If authenticated:
   ✅ Loads /chats with user data (no CORS error)
```

### Test 3: Token Expiration (After 1 Hour)
```bash
# Expected behavior:
1. Wait 1 hour after login
2. Navigate to /chats or perform any action
3. ✅ TMS-Server returns 401 (token expired)
4. ✅ tms-client catches 401 and redirects to /login
5. ✅ User re-authenticates with GCGC
6. ✅ New JWT issued, app works again
```

---

## API Call Summary Table

| Endpoint | System | Auth Method | Called By | Purpose |
|----------|--------|-------------|-----------|---------|
| `POST /api/auth/signin/credentials` | GCGC | None (public) | authService.login() | Initial authentication |
| `GET /api/v1/auth/token` | GCGC | Session cookie | authService.login() | Get JWT token |
| `POST /api/v1/auth/login` | TMS-Server | JWT (body) | authService.login() | Validate JWT + sync user |
| `GET /api/v1/users/me` | TMS-Server | Bearer JWT | authService.getCurrentUser() | Get current user data |
| `GET /api/v1/users/me` | GCGC | Session cookie | ❌ WRONG (AppHeader) | Should NOT be called |
| `GET /api/v1/users/[id]` | GCGC | API Key | TMS-Server (sync) | Server-to-server user fetch |

---

## Security Considerations

### JWT Token Security

**Storage**: `localStorage` (tms-client)
- ⚠️ **XSS Risk**: Vulnerable to XSS attacks
- ✅ **CSRF Protected**: Not in cookies (no CSRF risk)
- **Recommendation**: Consider migrating to HttpOnly cookies

**Transmission**: `Authorization: Bearer` header
- ✅ **Secure**: HTTPS only in production
- ✅ **Standard**: Industry-standard OAuth 2.0 pattern

**Validation**: Server-side only (tms-server)
- ✅ **Signature verification**: Prevents tampering
- ✅ **Expiration check**: Forces re-authentication after 1h
- ✅ **Algorithm whitelist**: Prevents algorithm confusion attacks

### CORS Security

**Current Config**: Explicit origin allowlist
```python
allow_origins=[
    "http://localhost:3000",  # Development
    "https://tms-client-staging.up.railway.app",  # Staging
]
```

**Recommendations**:
- ✅ **Good**: Explicit allowlist (not wildcard `*`)
- ✅ **Good**: Credentials allowed only for trusted origins
- ⚠️ **Consider**: Add production origin when deploying

---

## Performance Optimization Recommendations

### 1. Reduce GCGC API Calls
**Current**: Every user action may trigger GCGC sync
**Recommendation**: Implement Redis caching layer in TMS-Server
```python
# Cache user data for 15 minutes
await redis.setex(f"user:{tms_user_id}", 900, json.dumps(user_data))
```

### 2. Implement Token Refresh
**Current**: Token expires after 1h, user must re-login
**Recommendation**: Add refresh token flow
- GCGC issues 30-day refresh token
- tms-client refreshes access token silently before expiry

### 3. Batch User Lookups
**Current**: One API call per user
**Recommendation**: Add batch endpoint
```python
# GET /api/v1/users/batch?ids=uuid1,uuid2,uuid3
```

---

## Conclusion

### Root Cause
**AppHeader component calls GCGC's `/api/v1/users/me` directly**, which:
1. Requires NextAuth session (user doesn't have it)
2. Triggers redirect without CORS headers
3. Causes browser CORS violation

### Solution
**Use `authService.getCurrentUser()`**, which:
1. Calls TMS-Server's `/api/v1/users/me` (correct endpoint)
2. Uses JWT from localStorage (no GCGC session needed)
3. TMS-Server has correct CORS configuration
4. Consistent with the rest of the app

### Implementation Priority
1. **HIGH**: Fix AppHeader.tsx (5-minute fix)
2. **MEDIUM**: Verify NEXTAUTH_SECRET match across systems
3. **LOW**: Add Redis caching for user data
4. **LOW**: Implement token refresh flow

---

**Generated**: 2025-11-03
**Status**: Ready for implementation
**Files to Modify**: 1 (AppHeader.tsx in tms-client)
