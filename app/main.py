"""
FastAPI Application Entry Point.
Initializes the FastAPI app with middleware, CORS, and routes.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.cache import cache
from app.core.database import engine
from app.core.websocket import connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    await cache.connect()
    yield
    # Shutdown
    await cache.disconnect()
    await engine.dispose()


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# Initialize FastAPI application
app = FastAPI(
    title="TMS Messaging Server",
    description="FastAPI backend for team messaging application integrated with TMS",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Add rate limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Proxy Headers Middleware
# Railway uses a reverse proxy that terminates TLS and forwards requests via HTTP.
# This middleware reads X-Forwarded-Proto and X-Forwarded-Host headers to correctly
# detect HTTPS and construct proper URLs.
@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next):
    """
    Handle Railway's reverse proxy headers for correct HTTPS detection.

    Railway terminates TLS at the proxy and forwards requests via HTTP,
    so request.url.scheme returns 'http' even though the client connection is HTTPS.
    This middleware reads X-Forwarded-Proto and X-Forwarded-Host to fix this.
    """
    # Read forwarded headers from Railway's proxy
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")

    # Override scheme if forwarded proto exists (e.g., 'https')
    if forwarded_proto:
        request.scope["scheme"] = forwarded_proto

    # Override host if forwarded host exists
    if forwarded_host:
        # Set server tuple (host, port)
        port = 443 if forwarded_proto == "https" else 80
        request.scope["server"] = (forwarded_host, port)

    response = await call_next(request)
    return response


# CORS Middleware
# Note: For WebSocket connections, CORS is handled by Socket.IO itself (via cors_allowed_origins)
# Convert comma-separated string to list for CORS middleware
cors_origins = settings.get_allowed_origins_list()
print(f"🌐 CORS allowed origins: {cors_origins}")  # Debug log

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# HTTPException Handler with CORS
# Handles HTTP exceptions (401, 403, 404, etc.) while preserving status codes
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTP exceptions (401, 403, 404, etc.) with proper CORS headers.

    This preserves the original status code from HTTPException instead of
    converting everything to 500.
    """
    from fastapi.exceptions import HTTPException

    # Get origin from request headers (for proper CORS)
    origin = request.headers.get("origin", "*")

    # Return JSON error with CORS headers and ORIGINAL status code
    return JSONResponse(
        status_code=exc.status_code,  # Preserve original status code (401, 403, etc.)
        content={
            "detail": exc.detail
        },
        headers={
            "Access-Control-Allow-Origin": origin if origin in cors_origins else cors_origins[0] if cors_origins else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            **({"WWW-Authenticate": exc.headers.get("WWW-Authenticate")} if exc.headers and "WWW-Authenticate" in exc.headers else {})
        }
    )


# Global Exception Handler for CORS
# Ensures CORS headers are present even when errors occur
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that ensures CORS headers are always present.

    This is critical for message search and other features where database
    errors might occur before CORS middleware can add headers.

    NOTE: This only handles non-HTTP exceptions. HTTPException is handled
    by http_exception_handler above to preserve status codes.
    """
    import traceback
    import logging

    logger = logging.getLogger(__name__)
    logger.error(f"🔴 Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(f"📍 Request: {request.method} {request.url}")
    logger.error(f"📋 Traceback:\n{traceback.format_exc()}")

    # Get origin from request headers (for proper CORS)
    origin = request.headers.get("origin", "*")

    # Return JSON error with CORS headers
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal error occurred while processing your request",
                "type": type(exc).__name__
            }
        },
        headers={
            "Access-Control-Allow-Origin": origin if origin in cors_origins else cors_origins[0] if cors_origins else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


# Health Check Endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "environment": settings.environment,
        }
    )


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint.
    Verifies database, cache, and GCGC User Management System connectivity.
    """
    from app.core.tms_client import tms_client

    checks = {
        "database": False,
        "redis": "not_configured" if not settings.redis_url else False,
        "gcgc_user_management": False,
    }

    # Check database
    try:
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception:
        pass

    # Check Redis (only if configured)
    if settings.redis_url:
        try:
            checks["redis"] = await cache.exists("health_check")
        except Exception:
            pass

    # Check GCGC User Management System
    try:
        checks["gcgc_user_management"] = await tms_client.health_check()
    except Exception:
        pass

    # Consider redis as healthy if not configured
    redis_ok = checks["redis"] == "not_configured" or checks["redis"] is True
    all_healthy = checks["database"] and redis_ok and checks["gcgc_user_management"]
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not ready",
            "checks": checks,
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "TMS Messaging Server API",
        "version": "1.0.3",  # Auto-create users + local DB auth
        "deployed_at": "2025-10-16T06:45:00Z",  # Timestamp to verify
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
    }


# WebSocket Health Check
@app.get("/health/websocket", tags=["Health"])
async def websocket_health_check():
    """
    WebSocket configuration health check.
    Returns WebSocket endpoint information for debugging.
    """
    from app.core.websocket import connection_manager

    return JSONResponse(
        status_code=200,
        content={
            "status": "configured",
            "websocket_endpoint": "/socket.io/",
            "active_connections": len(connection_manager.connections),
            "active_users": len(connection_manager.user_sessions),
            "active_conversations": len(connection_manager.conversation_rooms),
            "config": {
                "transports": ["websocket"],
                "path": "/socket.io",
                "cors_origins": settings.allowed_origins,
                "heartbeat_interval": settings.ws_heartbeat_interval,
                "max_connections": settings.ws_max_connections,
            },
            "client_config": {
                "url": "wss://tms-chat-staging.example.com" if not settings.is_development else "ws://localhost:8000",
                "path": "/socket.io",
                "transports": ["websocket"],
                "upgrade": False,
            }
        }
    )


# Include API routers
from app.api.v1 import messages, conversations, users, auth, polls, notifications

app.include_router(
    messages.router,
    prefix="/api/v1/messages",
    tags=["Messages"]
)

app.include_router(
    conversations.router,
    prefix="/api/v1/conversations",
    tags=["Conversations"]
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"]
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    polls.router,
    prefix="/api/v1/polls",
    tags=["Polls"]
)

app.include_router(
    notifications.router,
    prefix="/api/v1/notifications",
    tags=["Notifications"]
)

# Wrap FastAPI with Socket.IO
# According to python-socketio docs, Socket.IO should wrap the ASGI app, not be mounted inside it
# This creates a combined ASGI app where Socket.IO handles /socket.io/* and FastAPI handles everything else
from app.core.websocket import connection_manager

# Save reference to FastAPI app (for testing/debugging)
fastapi_app = app

# Wrap FastAPI inside Socket.IO ASGIApp - this becomes the final ASGI app
# Client connects to: wss://domain/socket.io/?EIO=4&transport=websocket
app = connection_manager.get_asgi_app(fastapi_app)
