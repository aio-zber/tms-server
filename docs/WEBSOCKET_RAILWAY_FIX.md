# WebSocket Railway Deployment Fix

## Date: 2025-10-16

## Problem Summary

WebSocket connections to Railway deployment were failing with generic "websocket error" at:
```
wss://tms-server-staging.up.railway.app/ws/socket.io/?EIO=4&transport=websocket
```

## Root Cause Analysis

### 1. Path Configuration Mismatch
- **Server**: Socket.IO ASGI app mounted at `/ws` with `socketio_path='socket.io'`
- **Final endpoint**: `/ws/socket.io/` (Socket.IO automatically appends trailing slash)
- **Client**: Was correctly configured with `path: '/ws/socket.io'`
- **Issue**: Configuration was actually correct, but needed verification and consistency

### 2. WebSocket URL Generation
- Client's `WS_URL` was not dynamically detecting Railway environment
- Relied on environment variables that might not be set at build time
- Needed runtime detection based on `window.location.hostname`

### 3. Transport Configuration
- Polling transport unreliable on Railway
- Needed strict WebSocket-only mode with `upgrade: false`

## Applied Fixes

### Backend Changes

#### File: `/app/core/websocket.py`

1. **Added initialization logging** (lines 27-46):
```python
logger.info("Initializing ConnectionManager with WebSocket-only mode")
logger.info(f"CORS allowed origins: {settings.allowed_origins}")
# ... Socket.IO server initialization
logger.info("Socket.IO server initialized successfully")
logger.info(f"WebSocket endpoint: /ws/socket.io/ (mount point: /ws, socketio_path: socket.io)")
```

2. **Clarified socketio_path documentation** (lines 412-428):
```python
def get_asgi_app(self):
    """
    Critical: socketio_path is the path WITHIN the mounted app.
    Since this app is mounted at '/ws', Socket.IO will listen at '/ws/{socketio_path}'.
    The default socketio_path is 'socket.io/', so final URL is '/ws/socket.io/'.

    Client should connect to base URL with path='/ws/socket.io'
    """
    return socketio.ASGIApp(
        self.sio,
        socketio_path='socket.io'  # Socket.IO path (appended to mount point '/ws')
    )
```

#### File: `/app/main.py`

1. **Added WebSocket health check endpoint** (lines 129-160):
```python
@app.get("/health/websocket", tags=["Health"])
async def websocket_health_check():
    """
    WebSocket configuration health check.
    Returns WebSocket endpoint information for debugging.
    """
    return {
        "status": "configured",
        "websocket_endpoint": "/ws/socket.io/",
        "active_connections": len(connection_manager.connections),
        "active_users": len(connection_manager.user_sessions),
        "active_conversations": len(connection_manager.conversation_rooms),
        "config": {
            "transports": ["websocket"],
            "path": "/ws/socket.io",
            "cors_origins": settings.allowed_origins,
            "heartbeat_interval": settings.ws_heartbeat_interval,
            "max_connections": settings.ws_max_connections,
        },
        "client_config": {
            "url": "wss://tms-server-staging.up.railway.app",
            "path": "/ws/socket.io",
            "transports": ["websocket"],
            "upgrade": False,
        }
    }
```

### Frontend Changes

#### File: `/src/lib/constants.ts`

1. **Runtime WebSocket URL detection** (lines 54-89):
```typescript
const getWsUrl = () => {
  // Client-side: detect from window.location
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;

    // Railway deployment (production/staging)
    if (hostname.includes('railway.app')) {
      return 'wss://tms-server-staging.up.railway.app';
    }

    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'ws://localhost:8000';
    }
  }

  // Server-side or fallback: try environment variable
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (envUrl) {
    if (envUrl.includes('railway.app') && envUrl.startsWith('ws://')) {
      return envUrl.replace('ws://', 'wss://');
    }
    return envUrl;
  }

  return 'ws://localhost:8000';
};
```

#### File: `/src/features/chat/services/websocketService.ts`

1. **Updated Socket.IO client configuration** (lines 40-73):
```typescript
this.socket = io(WS_URL, {
  path: '/ws/socket.io',  // CRITICAL: Must match server mount point + socketio_path
  auth: { token },
  transports: ['websocket'],  // WebSocket-only for Railway
  upgrade: false,  // Don't upgrade from polling
  reconnection: true,
  reconnectionAttempts: this.maxReconnectAttempts,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 20000,  // Increased timeout for Railway
  autoConnect: true,
});
```

2. **Added debug logging**:
```typescript
console.log('[WebSocket] Connecting to:', WS_URL);
console.log('[WebSocket] Path: /ws/socket.io');
console.log('[WebSocket] Full URL:', `${WS_URL}/ws/socket.io/`);
```

#### File: `/src/lib/socket.ts`

1. **Updated Socket.IO client configuration** (lines 18-51):
```typescript
this.socket = io(SOCKET_URL, {
  path: '/ws/socket.io',  // Must match server mount point + socketio_path
  auth: { token },
  transports: ['websocket'],  // WebSocket-only transport
  upgrade: false,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: this.maxReconnectAttempts,
  timeout: 20000,  // Increased timeout for Railway
  autoConnect: true,
  forceNew: false,
});
```

## Deployment Steps

### 1. Deploy Backend to Railway

```bash
# From tms-server directory
git add .
git commit -m "fix: Configure WebSocket for Railway deployment with correct path and health check"
git push origin staging
```

Railway will automatically deploy when changes are pushed.

### 2. Verify Backend WebSocket Health

```bash
# Check WebSocket configuration
curl https://tms-server-staging.up.railway.app/health/websocket

# Expected response:
{
  "status": "configured",
  "websocket_endpoint": "/ws/socket.io/",
  "active_connections": 0,
  "active_users": 0,
  "active_conversations": 0,
  "config": {
    "transports": ["websocket"],
    "path": "/ws/socket.io",
    "cors_origins": ["https://tms-client-staging.up.railway.app"],
    ...
  },
  "client_config": {
    "url": "wss://tms-server-staging.up.railway.app",
    "path": "/ws/socket.io",
    "transports": ["websocket"],
    "upgrade": false
  }
}
```

### 3. Deploy Frontend to Railway

```bash
# From tms-client directory
git add .
git commit -m "fix: Update WebSocket client configuration for Railway deployment"
git push origin staging
```

### 4. Test WebSocket Connection

1. Open browser DevTools (Console tab)
2. Navigate to `https://tms-client-staging.up.railway.app`
3. Log in to the application
4. Check console logs:

```
[WebSocket] Connecting to: wss://tms-server-staging.up.railway.app
[WebSocket] Path: /ws/socket.io
[WebSocket] Full URL: wss://tms-server-staging.up.railway.app/ws/socket.io/
✅ WebSocket connected: <socket-id>
```

5. Navigate to Messages page and select a conversation
6. Verify console shows:

```
Joining conversation: <conversation-id>
[Socket] Joined conversation: <conversation-id>
```

## Environment Variables

### Backend (Railway - tms-server)

Ensure these are set in Railway dashboard:

```bash
# Required
DATABASE_URL=<Railway PostgreSQL URL>
DATABASE_URL_SYNC=<Railway PostgreSQL URL (sync)>
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
USER_MANAGEMENT_API_KEY=<TMS API key>
JWT_SECRET=<matches TMS NEXTAUTH_SECRET>
NEXTAUTH_SECRET=<matches TMS NEXTAUTH_SECRET>
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app
ENVIRONMENT=staging
DEBUG=true

# Optional
REDIS_URL=<Redis URL if configured>
```

### Frontend (Railway - tms-client)

```bash
# Optional - will auto-detect if not set
NEXT_PUBLIC_API_URL=https://tms-server-staging.up.railway.app/api/v1
NEXT_PUBLIC_WS_URL=wss://tms-server-staging.up.railway.app
NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
NEXT_PUBLIC_ENVIRONMENT=staging
```

**Note**: Frontend will auto-detect Railway environment at runtime, so these are optional.

## Troubleshooting

### Issue: WebSocket still fails to connect

**Check 1: CORS Configuration**
```bash
curl https://tms-server-staging.up.railway.app/health/websocket | jq '.config.cors_origins'
```
Should include your client URL.

**Check 2: Server Logs**
```bash
# In Railway dashboard, check tms-server logs for:
Initializing ConnectionManager with WebSocket-only mode
CORS allowed origins: ['https://tms-client-staging.up.railway.app']
Socket.IO server initialized successfully
WebSocket endpoint: /ws/socket.io/
```

**Check 3: Client Console**
Look for connection errors in browser DevTools console.

### Issue: Connection timeout

**Solution**: Increase timeout in client configuration (already set to 20000ms).

**Check**: Ensure Railway service is not sleeping (Pro plan needed for always-on).

### Issue: CORS errors

**Solution**: Add client URL to `ALLOWED_ORIGINS` in Railway backend environment variables:
```bash
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000
```

## Key Configuration Rules

1. **Server Mount Point**: `/ws` (defined in `main.py`)
2. **Socket.IO Path**: `socket.io` (defined in `websocket.py`)
3. **Final Endpoint**: `/ws/socket.io/` (automatic)
4. **Client Path**: `/ws/socket.io` (Socket.IO appends trailing slash)
5. **Transport**: `websocket` only (no polling on Railway)
6. **Upgrade**: `false` (direct WebSocket, no upgrade)
7. **Protocol**: `wss://` for Railway, `ws://` for localhost

## Testing Checklist

- [ ] Backend health check responds: `GET /health`
- [ ] WebSocket health check responds: `GET /health/websocket`
- [ ] Backend logs show initialization messages
- [ ] Client connects successfully (console logs)
- [ ] Client can join conversation rooms
- [ ] Real-time messages are received
- [ ] Typing indicators work
- [ ] User presence updates work

## Next Steps

1. Monitor Railway logs for WebSocket connection attempts
2. Test real-time messaging between multiple users
3. Verify reconnection logic works after network disruption
4. Load test with multiple concurrent WebSocket connections

## References

- Socket.IO Python Documentation: https://python-socketio.readthedocs.io/
- Socket.IO Client Documentation: https://socket.io/docs/v4/client-api/
- Railway WebSocket Documentation: https://docs.railway.app/reference/websockets
