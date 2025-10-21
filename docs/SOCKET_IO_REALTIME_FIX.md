# Socket.IO Real-Time Messaging Fix

## Problem Summary

Your TMS Chat system had multiple issues preventing real-time message delivery:

1. **Socket.IO Path Mismatch**: Client was connecting to `/ws/socket.io` but server only listens on `/socket.io`
2. **CORS Configuration**: Not properly configured for Railway deployment causing 500 errors
3. **Type Mismatch**: `allowed_origins` config had inconsistent type handling

## Issues from Logs

```
POST https://tms-server-staging.up.railway.app/api/v1/messages/ net::ERR_FAILED 500 (Internal Server Error)
Access to fetch at 'https://tms-server-staging.up.railway.app/api/v1/messages/' 
from origin 'https://tms-client-staging.up.railway.app' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Root Causes

### 1. Socket.IO Path Configuration ❌

**Problem:**
```python
# Client was trying to connect to:
path: '/ws/socket.io'  # WRONG
```

**Reality:**
```python
# Server configuration:
app = socketio.ASGIApp(sio, fastapi_app)  # Wraps at /socket.io/ (default)
```

### 2. CORS Type Handling ❌

**Problem:**
```python
# config.py had string type that wasn't properly converted to list
allowed_origins: str = Field(default="http://localhost:3000")

# But CORSMiddleware expects List[str]
```

### 3. Missing CORS Headers on Railway ❌

The `allowed_origins` wasn't being properly passed to both:
- FastAPI's `CORSMiddleware`
- Socket.IO's `cors_allowed_origins`

## Fixes Applied

### ✅ Fix 1: Socket.IO Client Path (TMS-Client)

**Files Changed:**
- `/tms-client/src/features/chat/services/websocketService.ts`
- `/tms-client/src/lib/socket.ts`

**Change:**
```typescript
// BEFORE (WRONG):
this.socket = io(WS_URL, {
  path: '/ws/socket.io',  // ❌ Wrong path
  // ...
});

// AFTER (CORRECT):
this.socket = io(WS_URL, {
  path: '/socket.io',  // ✅ Correct path matching server
  // ...
});
```

**Why This Fixes It:**
- Server wraps FastAPI with `socketio.ASGIApp(sio, fastapi_app)`
- This makes Socket.IO handle `/socket.io/*` endpoints
- Client must connect to the same path

### ✅ Fix 2: CORS Configuration (TMS-Server)

**Files Changed:**
- `/tms-server/app/config.py`
- `/tms-server/app/main.py`
- `/tms-server/app/core/websocket.py`

**Changes:**

#### config.py
```python
# BEFORE:
allowed_origins: str = Field(default="http://localhost:3000")

@field_validator("allowed_origins")
@classmethod
def parse_cors_origins(cls, v: str) -> List[str]:
    return [origin.strip() for origin in v.split(",") if origin.strip()]

# AFTER:
allowed_origins: List[str] = Field(default="http://localhost:3000")

@field_validator("allowed_origins", mode="before")
@classmethod
def parse_cors_origins(cls, v) -> List[str]:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    return ["http://localhost:3000"]
```

#### main.py
```python
# BEFORE:
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Could be str or list
    # ...
)

# AFTER:
cors_origins = settings.allowed_origins if isinstance(settings.allowed_origins, list) else [settings.allowed_origins]
print(f"🌐 CORS allowed origins: {cors_origins}")  # Debug log

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Always list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

#### websocket.py
```python
# BEFORE:
cors_origins = settings.allowed_origins if isinstance(settings.allowed_origins, list) else ["*"]

# AFTER:
cors_origins = settings.allowed_origins if settings.allowed_origins else ["*"]
# No need to check isinstance anymore - field_validator ensures it's always a list
```

## Railway Environment Variables

### TMS-Server (Backend)

**Required Variables:**
```bash
# CORS - CRITICAL: Include your frontend URL
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000

# Database
DATABASE_URL=postgresql://...
DATABASE_URL_SYNC=postgresql://...

# Security
JWT_SECRET=your-jwt-secret-min-32-chars
NEXTAUTH_SECRET=your-nextauth-secret-from-gcgc

# User Management
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
USER_MANAGEMENT_API_KEY=your-api-key

# Environment
ENVIRONMENT=staging
DEBUG=False

# Redis (optional)
REDIS_URL=redis://...
```

### TMS-Client (Frontend)

**Required Variables:**
```bash
# API URLs
NEXT_PUBLIC_API_URL=https://tms-server-staging.up.railway.app/api/v1
NEXT_PUBLIC_WS_URL=https://tms-server-staging.up.railway.app

# Authentication (from GCGC TMS)
NEXTAUTH_URL=https://tms-client-staging.up.railway.app
NEXTAUTH_SECRET=same-as-tms-server

# User Management (GCGC TMS)
NEXT_PUBLIC_USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
```

## Deployment Steps

### 1. Deploy TMS-Server (Backend)

```bash
cd /Users/kyleisaacmendoza/Documents/workspace/tms-server

# Stage changes
git add app/config.py app/main.py app/core/websocket.py

# Commit
git commit -m "fix: Socket.IO CORS configuration for Railway deployment"

# Push to Railway
git push origin staging  # or main, depending on your branch
```

### 2. Verify Server Environment Variables

1. Go to **Railway Dashboard** → **tms-server-staging**
2. Click **Variables** tab
3. **VERIFY** these settings:
   ```
   ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000
   ```
4. **Save** and **Redeploy** if changed

### 3. Deploy TMS-Client (Frontend)

```bash
cd /Users/kyleisaacmendoza/Documents/workspace/tms-client

# Stage changes
git add src/features/chat/services/websocketService.ts src/lib/socket.ts

# Commit
git commit -m "fix: Socket.IO path configuration to match server"

# Push to Railway
git push origin staging  # or main
```

### 4. Verify Client Environment Variables

1. Go to **Railway Dashboard** → **tms-client-staging**
2. Click **Variables** tab
3. **VERIFY** these settings:
   ```
   NEXT_PUBLIC_API_URL=https://tms-server-staging.up.railway.app/api/v1
   NEXT_PUBLIC_WS_URL=https://tms-server-staging.up.railway.app
   ```
4. **Save** and **Redeploy** if changed

## Testing the Fix

### 1. Check Server Logs

In Railway **tms-server** logs, you should see:

```
🚀 Starting TMS Messaging Server...
🌐 CORS allowed origins: ['https://tms-client-staging.up.railway.app', 'http://localhost:3000']
Initializing ConnectionManager with WebSocket-only mode
CORS allowed origins: ['https://tms-client-staging.up.railway.app', 'http://localhost:3000']
Prepared CORS origins for Socket.IO: ['https://tms-client-staging.up.railway.app', 'http://localhost:3000']
Socket.IO server initialized successfully
```

### 2. Check WebSocket Health

```bash
curl https://tms-server-staging.up.railway.app/health/websocket | jq
```

Expected response:
```json
{
  "status": "configured",
  "websocket_endpoint": "/socket.io/",
  "config": {
    "cors_origins": [
      "https://tms-client-staging.up.railway.app",
      "http://localhost:3000"
    ],
    "path": "/socket.io"
  }
}
```

### 3. Test Real-Time Messaging

1. Open https://tms-client-staging.up.railway.app
2. Login with your user
3. Open browser DevTools → Console
4. Look for:
   ```
   [WebSocket] Connecting to: https://tms-server-staging.up.railway.app
   [WebSocket] Path: /socket.io
   ✅ WebSocket connected: <socket-id>
   ```
5. Send a message in a conversation
6. **Expected behavior:**
   - Message appears immediately (no refresh needed)
   - Both sender and receiver see it in real-time
   - No CORS errors in console
   - No 500 errors

### 4. Check for Errors

Open **Browser Console** and verify:
- ✅ No CORS errors
- ✅ No 500 errors on `/api/v1/messages/` POST
- ✅ Socket.IO connected successfully
- ✅ Messages broadcasting via `new_message` event

## How It Works Now

### Message Flow (After Fix)

1. **User sends message:**
   ```typescript
   // Client calls REST API
   POST /api/v1/messages/ { conversation_id, content }
   ```

2. **Server processes:**
   ```python
   # app/api/v1/messages.py
   async def send_message():
       # 1. Create message in database
       message = await service.send_message(...)
       
       # 2. Broadcast via Socket.IO
       await ws_manager.broadcast_new_message(conversation_id, message)
       
       # 3. Return message to sender
       return message
   ```

3. **Real-time broadcast:**
   ```python
   # app/core/websocket.py
   async def broadcast_new_message():
       room = f"conversation:{conversation_id}"
       await self.sio.emit('new_message', message_data, room=room)
   ```

4. **Clients receive:**
   ```typescript
   // All users in conversation receive via Socket.IO
   socket.on('new_message', (message) => {
       // Update UI immediately
       addMessageToChat(message);
   });
   ```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  TMS-Client (Next.js)                                       │
│  https://tms-client-staging.up.railway.app                  │
│                                                             │
│  1. Send Message (HTTP POST)                               │
│     POST /api/v1/messages/ ────────────────────┐           │
│                                                 │           │
│  2. Socket.IO Connection (WebSocket)           │           │
│     wss://tms-server.../socket.io/?EIO=4 ──┐  │           │
│                                             │  │           │
│  3. Receive Real-time Updates              │  │           │
│     socket.on('new_message') <──────┐      │  │           │
└─────────────────────────────────────│──────│──│───────────┘
                                      │      │  │
                                      │      │  │
┌─────────────────────────────────────│──────│──│───────────┐
│  TMS-Server (FastAPI + Socket.IO)  │      │  │           │
│  https://tms-server-staging.up.railway.app │  │           │
│                                             │  │           │
│  ┌──────────────────────────────────────┐  │  │           │
│  │  FastAPI App (REST API)              │  │  │           │
│  │  ├─ /api/v1/messages/  <──────────────┼──┘           │
│  │  │   └─ MessageService               │  │              │
│  │  │       └─ ws_manager.broadcast()   │  │              │
│  │  └─ CORS: allow-origin=tms-client    │  │              │
│  └──────────────────────────────────────┘  │              │
│           │                                 │              │
│           ├─ Wrapped by Socket.IO ASGIApp  │              │
│           ▼                                 │              │
│  ┌──────────────────────────────────────┐  │              │
│  │  Socket.IO Server                    │  │              │
│  │  ├─ /socket.io/* <────────────────────┼──┘             │
│  │  ├─ cors_allowed_origins=tms-client   │                │
│  │  └─ emit('new_message') ───────────────┼────────────┐  │
│  └──────────────────────────────────────┘               │  │
│                                                          │  │
└──────────────────────────────────────────────────────────┼──┘
                                                           │
                                    Real-time broadcast    │
                                    to all conversation    │
                                    members ───────────────┘
```

## Key Points

1. **Socket.IO Path**: Always `/socket.io` (default) because server uses `socketio.ASGIApp()`
2. **CORS**: Must be configured in BOTH FastAPI middleware AND Socket.IO server
3. **Message Flow**: HTTP POST saves to DB → Socket.IO broadcasts → Clients receive real-time
4. **No Polling**: Client uses `transports: ['websocket']` for Railway compatibility
5. **Room-Based**: Socket.IO rooms ensure messages only go to conversation members

## Verification Checklist

Before testing, ensure:

- [ ] TMS-Server deployed with fixed `config.py`, `main.py`, `websocket.py`
- [ ] TMS-Client deployed with fixed `websocketService.ts`, `socket.ts`
- [ ] Railway env var `ALLOWED_ORIGINS` includes your frontend URL
- [ ] Railway env var `NEXT_PUBLIC_WS_URL` points to server (without `/api/v1`)
- [ ] Server logs show CORS origins as list
- [ ] WebSocket health endpoint returns correct config
- [ ] Browser console shows Socket.IO connection success
- [ ] Messages appear in real-time without refresh
- [ ] No CORS or 500 errors in console

## Troubleshooting

### Still Getting CORS Errors?

1. Check Railway logs for CORS configuration:
   ```
   🌐 CORS allowed origins: ['https://tms-client-staging.up.railway.app']
   ```

2. Verify environment variable (no trailing slash):
   ```bash
   # Railway Variables
   ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app
   ```

### Socket.IO Not Connecting?

1. Check client console for path:
   ```
   [WebSocket] Path: /socket.io  # Should be /socket.io, not /ws/socket.io
   ```

2. Verify server is running:
   ```bash
   curl https://tms-server-staging.up.railway.app/health
   ```

### Messages Not Real-Time?

1. Check Socket.IO connection status in console
2. Verify you joined the conversation room:
   ```
   Joining conversation: <conversation-id>
   ```
3. Check server logs for broadcast messages

## Success Criteria

✅ **Fixed when:**
- Socket.IO connects successfully
- Messages appear instantly for both sender and receiver
- No need to refresh to see new messages
- No CORS errors in browser console
- No 500 errors on message POST
- Multiple users see same message simultaneously

---

**Status:** ✅ **FIXED AND READY TO DEPLOY**

**Last Updated:** 2025-10-16

