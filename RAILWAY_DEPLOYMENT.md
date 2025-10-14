# Railway Deployment Guide - TMS Server

## ⚠️ BREAKING CHANGE: Environment Variable Rename

**Date**: 2025-10-14

Environment variables have been renamed for clarity. See `MIGRATION_AUTH_FIX.md` for full migration guide.

## Previous Issues Fixed

1. **Redis connection failure** - Server now runs without Redis if no `REDIS_URL` is provided
2. **Health check timeout** - `/health` endpoint handles missing services gracefully
3. **Wrong API URL** - TMS_API_URL was pointing to frontend instead of GCGC backend
4. **JWT Secret Mismatch** - JWT_SECRET didn't match GCGC's NEXTAUTH_SECRET

## Railway Environment Variables

Set these in your Railway dashboard:

### Required Variables (NEW NAMES)
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
DATABASE_URL_SYNC=postgresql://user:pass@host:port/db
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
USER_MANAGEMENT_API_KEY=REDACTED_API_KEY
JWT_SECRET=REDACTED_JWT_SECRET
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app
ENVIRONMENT=staging
DEBUG=true
```

⚠️ **CRITICAL**:
- `USER_MANAGEMENT_API_URL` must point to **GCGC backend** (not TMS-Client frontend!)
- `JWT_SECRET` must match GCGC's `NEXTAUTH_SECRET` exactly

### Optional Variables
```bash
REDIS_URL=redis://redis-host:port/0  # Leave empty to run without Redis
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Health Check Endpoints

- **Basic health**: `GET /health` - Always returns 200 if server is running
- **Readiness check**: `GET /health/ready` - Checks database, GCGC User Management, and Redis (if configured)

Railway should use `/health` for health checks.

Expected `/health/ready` response:
```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "redis": "not_configured",
    "gcgc_user_management": true
  }
}
```

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