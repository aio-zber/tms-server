"""
FastAPI Application Entry Point.
Initializes the FastAPI app with middleware, CORS, and routes.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.cache import cache
from app.core.database import engine
# from app.core.websocket import connection_manager


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


# Initialize FastAPI application
app = FastAPI(
    title="TMS Messaging Server",
    description="FastAPI backend for team messaging application integrated with TMS",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
    Verifies database and cache connectivity.
    """
    from app.core.tms_client import tms_client

    checks = {
        "database": False,
        "redis": "not_configured" if not settings.redis_url else False,
        "tms": False,
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

    # Check TMS
    try:
        checks["tms"] = await tms_client.health_check()
    except Exception:
        pass

    # Consider redis as healthy if not configured
    redis_ok = checks["redis"] == "not_configured" or checks["redis"] is True
    all_healthy = checks["database"] and redis_ok and checks["tms"]
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
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
    }


# Include API routers
from app.api.v1 import messages, conversations, users, auth

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

# Mount WebSocket
# connection_manager.mount_to_app(app)
