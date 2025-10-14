# Railway Deployment Guide - TMS Server

## Issue Fixed

The deployment was failing because:
1. **Redis connection failure** - The server tried to connect to `redis://localhost:6379/0` which doesn't exist on Railway
2. **Health check timeout** - The `/health` endpoint was unreachable due to startup failures

## Solution Applied

✅ **Made Redis optional** - Server now runs without Redis if no `REDIS_URL` is provided
✅ **Updated health checks** - `/health/ready` endpoint handles missing Redis gracefully
✅ **Added error handling** - Cache operations fail silently when Redis is unavailable

## Railway Environment Variables

Set these in your Railway dashboard:

### Required Variables
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
DATABASE_URL_SYNC=postgresql://user:pass@host:port/db
TMS_API_URL=https://gcgc-team-management-system-staging.up.railway.app
TMS_API_KEY=REDACTED_JWT_SECRET
JWT_SECRET=REDACTED_JWT_SECRET
ALLOWED_ORIGINS=https://your-frontend-domain.com
ENVIRONMENT=production
DEBUG=false
```

### Optional Variables
```bash
REDIS_URL=redis://redis-host:port/0  # Leave empty to run without Redis
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Health Check Endpoints

- **Basic health**: `GET /health` - Always returns 200 if server is running
- **Readiness check**: `GET /health/ready` - Checks database, TMS, and Redis (if configured)

Railway should use `/health` for health checks.

## Deployment Commands

Railway will automatically detect and use:
```bash
# Build
pip install -r requirements.txt

# Start  
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Database Migration

Run this after first deployment:
```bash
# In Railway console
alembic upgrade head
```

## Testing the Deployment

1. Check basic health: `curl https://your-app.up.railway.app/health`
2. Check readiness: `curl https://your-app.up.railway.app/health/ready`
3. View API docs: `https://your-app.up.railway.app/docs` (if DEBUG=true)

## Performance Notes

- **Without Redis**: User data is fetched from TMS on every request (slower but functional)
- **With Redis**: User data is cached for better performance
- **Recommendation**: Add Redis service for production workloads