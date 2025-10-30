# Environment Variables Setup Guide

This guide explains how to configure environment variables for the TMS Server to fix CORS and authentication issues.

## 🔑 Required Environment Variables

### For Railway Deployment

Set these variables in your Railway dashboard under **Settings → Variables**:

```bash
# ========================================
# CRITICAL: CORS Configuration
# ========================================
# MUST include the TMS Client URL to prevent CORS errors
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000

# ========================================
# Database Configuration
# ========================================
DATABASE_URL=postgresql://user:password@host:port/database
DATABASE_URL_SYNC=postgresql://user:password@host:port/database

# ========================================
# GCGC Integration (User Management)
# ========================================
# URL of the GCGC Team Management System
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app

# API key for server-to-server communication with GCGC
USER_MANAGEMENT_API_KEY=your_api_key_here

# Request timeout in seconds
USER_MANAGEMENT_API_TIMEOUT=30

# ========================================
# JWT Configuration
# ========================================
# CRITICAL: Must match GCGC's NEXTAUTH_SECRET exactly!
JWT_SECRET=your_jwt_secret_min_32_characters_long
NEXTAUTH_SECRET=your_jwt_secret_min_32_characters_long

# JWT settings
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ========================================
# Application Settings
# ========================================
ENVIRONMENT=staging
DEBUG=false

# ========================================
# Redis (Optional)
# ========================================
REDIS_URL=redis://default:password@host:port

# ========================================
# Alibaba Cloud OSS (Optional)
# ========================================
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_BUCKET_NAME=
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_REGION=cn-hangzhou

# ========================================
# Rate Limiting
# ========================================
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# ========================================
# WebSocket
# ========================================
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=10000

# ========================================
# Logging
# ========================================
LOG_LEVEL=INFO
LOG_FORMAT=json

# ========================================
# Sentry (Optional)
# ========================================
SENTRY_DSN=
SENTRY_ENVIRONMENT=staging
```

## 🚨 Critical Configuration for CORS Fix

The most important variable for fixing the CORS error is:

```bash
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000
```

### How to Set in Railway:

1. Go to your Railway project
2. Click on **tms-server** service
3. Go to **Settings** tab
4. Scroll to **Variables** section
5. Click **+ New Variable**
6. Add:
   - **Name:** `ALLOWED_ORIGINS`
   - **Value:** `https://tms-client-staging.up.railway.app,http://localhost:3000`
7. Click **Add**
8. Railway will automatically redeploy with the new variable

### ✅ Verification

After setting the variable, verify it's working:

```bash
# Run the test script
./test_auth_flow.sh

# Or manually check CORS headers
curl -i -X OPTIONS \
  -H "Origin: https://tms-client-staging.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  https://tms-server-staging.up.railway.app/api/v1/auth/login
```

You should see:
```
access-control-allow-origin: https://tms-client-staging.up.railway.app
access-control-allow-credentials: true
access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
access-control-allow-headers: *
```

## 🔒 JWT Secret Configuration

**CRITICAL:** The `JWT_SECRET` and `NEXTAUTH_SECRET` must **exactly match** the secret used by GCGC's NextAuth configuration.

### Why This Matters:

1. GCGC generates JWT tokens using `NEXTAUTH_SECRET`
2. TMS Server validates these tokens using `JWT_SECRET` / `NEXTAUTH_SECRET`
3. If they don't match, all authentications will fail with "Invalid signature"

### How to Get the Correct Secret:

1. Contact the GCGC team
2. Ask for the `NEXTAUTH_SECRET` value
3. Set both `JWT_SECRET` and `NEXTAUTH_SECRET` to that value

## 📝 Environment-Specific Configurations

### Development (.env file)

```bash
# .env (for local development)
DATABASE_URL=postgresql://postgres:password@localhost:5432/tms_dev
DATABASE_URL_SYNC=postgresql://postgres:password@localhost:5432/tms_dev
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
USER_MANAGEMENT_API_URL=http://localhost:3002
JWT_SECRET=dev_secret_min_32_characters_long_change_in_prod
NEXTAUTH_SECRET=dev_secret_min_32_characters_long_change_in_prod
ENVIRONMENT=development
DEBUG=true
REDIS_URL=redis://localhost:6379
```

### Staging (Railway)

```bash
DATABASE_URL=<from Railway PostgreSQL addon>
DATABASE_URL_SYNC=<from Railway PostgreSQL addon>
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
JWT_SECRET=<get from GCGC team>
NEXTAUTH_SECRET=<get from GCGC team>
USER_MANAGEMENT_API_KEY=<get from GCGC team>
ENVIRONMENT=staging
DEBUG=false
REDIS_URL=<from Railway Redis addon>
```

### Production (Railway)

```bash
DATABASE_URL=<from Railway PostgreSQL addon>
DATABASE_URL_SYNC=<from Railway PostgreSQL addon>
ALLOWED_ORIGINS=https://tms-client.your-domain.com
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system.your-domain.com
JWT_SECRET=<strong production secret>
NEXTAUTH_SECRET=<strong production secret>
USER_MANAGEMENT_API_KEY=<production API key>
ENVIRONMENT=production
DEBUG=false
REDIS_URL=<from Railway Redis addon>
```

## 🧪 Testing Your Configuration

### 1. Check Environment Variables are Loaded

```bash
# SSH into Railway container
railway shell

# Check if variables are set
echo $ALLOWED_ORIGINS
echo $USER_MANAGEMENT_API_URL
echo $JWT_SECRET
```

### 2. Test CORS Configuration

```bash
# Run the test script
./test_auth_flow.sh

# Or use curl directly
curl -i https://tms-server-staging.up.railway.app/health
# Should show CORS headers
```

### 3. Test Authentication Endpoint

```bash
# Test with invalid token (should return 401 with CORS headers)
curl -i -X POST \
  -H "Origin: https://tms-client-staging.up.railway.app" \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid"}' \
  https://tms-server-staging.up.railway.app/api/v1/auth/login
```

## 🔧 Troubleshooting

### Issue: CORS errors persist

**Solution:**
1. Verify `ALLOWED_ORIGINS` is set correctly in Railway
2. Check Railway logs: `railway logs`
3. Look for: `🌐 CORS allowed origins: [...]`
4. Ensure client URL is in the list
5. Redeploy if needed: `railway up`

### Issue: Authentication fails with "Invalid signature"

**Solution:**
1. Verify `JWT_SECRET` matches GCGC's `NEXTAUTH_SECRET`
2. Contact GCGC team to confirm the secret
3. Update in Railway and redeploy

### Issue: "User not found" errors

**Solution:**
1. Check `USER_MANAGEMENT_API_URL` points to correct GCGC instance
2. Verify `USER_MANAGEMENT_API_KEY` is valid
3. Test GCGC API manually:
```bash
curl -H "X-API-Key: $USER_MANAGEMENT_API_KEY" \
  https://gcgc-team-management-system-staging.up.railway.app/health
```

## 📊 Configuration Checklist

- [ ] `ALLOWED_ORIGINS` includes TMS Client URL
- [ ] `DATABASE_URL` is set (from Railway addon)
- [ ] `USER_MANAGEMENT_API_URL` points to GCGC
- [ ] `USER_MANAGEMENT_API_KEY` is valid
- [ ] `JWT_SECRET` matches GCGC's `NEXTAUTH_SECRET`
- [ ] `NEXTAUTH_SECRET` matches GCGC's secret
- [ ] `ENVIRONMENT` is set correctly
- [ ] CORS headers appear in responses
- [ ] Health check endpoint works
- [ ] Authentication endpoint accessible

## 🚀 Deployment

After setting all variables:

1. **Railway auto-deploys** when variables change
2. **Wait for deployment** to complete (~2-3 minutes)
3. **Check logs** for startup messages:
   ```bash
   railway logs
   ```
4. **Look for:**
   ```
   🌐 CORS allowed origins: ['https://tms-client-staging.up.railway.app', 'http://localhost:3000']
   ✅ Database connected
   ✅ Redis connected
   ```
5. **Run tests:**
   ```bash
   ./test_auth_flow.sh
   ```

## 📞 Support

If issues persist:

1. Check Railway logs: `railway logs --tail 100`
2. Verify environment variables in Railway dashboard
3. Run test script: `./test_auth_flow.sh`
4. Contact DevOps team with error logs

---

**Last Updated:** 2025-01-23
**Related Docs:** CLIENT_AUTH_GUIDE.md, README.md
