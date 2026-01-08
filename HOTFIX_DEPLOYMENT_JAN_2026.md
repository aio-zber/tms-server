# Hotfix Deployment: Fix 500/401 Errors and Security Issues
**Date**: January 8, 2026  
**Target**: Alibaba Cloud Staging & Production  
**Priority**: CRITICAL

## Summary of Changes

This deployment includes critical fixes for authentication errors and a security vulnerability:

### 1. Fixed 401 → 500 Error Conversion ✅
- **Problem**: Backend was returning 500 Internal Server Error instead of 401 Unauthorized
- **Root Cause**: Generic exception handlers were catching HTTPException(401) and converting them to 500
- **Fix**: Added specific HTTPException handler to preserve original status codes
- **Files Modified**:
  - `app/dependencies.py` - Added `except HTTPException: raise` before generic exception handler
  - `app/main.py` - Added dedicated `@app.exception_handler(HTTPException)` to preserve status codes

### 2. Increased JWT Token Expiration ✅
- **Problem**: Tokens expiring too quickly (24 hours)
- **Fix**: Increased to 30 days (720 hours)
- **Files Modified**:
  - `.env` - Updated `JWT_EXPIRATION_HOURS=720`

### 3. Updated CORS Configuration ✅
- **Problem**: Alibaba Cloud domains not in allowed origins
- **Fix**: Added production and staging Alibaba Cloud domains
- **Files Modified**:
  - `.env` - Added Alibaba Cloud domains to ALLOWED_ORIGINS

### 4. Implemented Single-Use Token Security 🔒
- **Problem**: GCGC tokens are reusable for 30 days, creating replay attack vulnerability
- **Fix**: Implemented Redis-based single-use token tracking
- **Files Modified**:
  - `app/api/v1/auth.py` - Added single-use validation to `/login/sso` endpoint

---

## Deployment Steps

### Step 1: Update Alibaba Cloud Environment Variables

**CRITICAL**: Update these on Alibaba Cloud server BEFORE deploying code:

```bash
# SSH into staging server
ssh root@47.80.66.95

# Navigate to application directory
cd /var/www/tms-server

# Edit environment file
nano .env

# Update these values:
JWT_EXPIRATION_HOURS=720
ALLOWED_ORIGINS=https://tms-chat-staging.example.com,https://tms-chat.example.com
ALLOWED_HOSTS=tms-chat-staging.example.com,tms-chat.example.com

# Save and exit (Ctrl+X, Y, Enter)
```

### Step 2: Deploy Backend Code

```bash
# Still on server
cd /var/www/tms-server

# Pull latest changes
git fetch origin
git checkout staging
git pull origin staging

# Restart the backend service
pm2 restart tms-server
# OR if using systemd:
systemctl restart tms-server

# Check status
pm2 status
# OR
systemctl status tms-server
```

### Step 3: Verify Deployment

```bash
# Test health endpoint
curl https://tms-chat-staging.example.com/health

# Test authentication (should return 401, not 500 for invalid token)
curl https://tms-chat-staging.example.com/api/v1/conversations/ \
  -H "Authorization: Bearer invalid_token"
```

---

## Environment Variables Summary

**Update these on Alibaba Cloud:**

| Variable | New Value | Current Value |
|----------|-----------|---------------|
| `JWT_EXPIRATION_HOURS` | `720` | `24` |
| `ALLOWED_ORIGINS` | `https://tms-chat-staging.example.com,https://tms-chat.example.com` | `http://localhost:3000` |
| `ALLOWED_HOSTS` | `tms-chat-staging.example.com,tms-chat.example.com` | `localhost,127.0.0.1` |

---

## Testing Checklist

After deployment, verify:

- [ ] Health endpoint returns 200 OK
- [ ] 401 errors return as 401 (not 500)
- [ ] SSO authentication works
- [ ] Conversations load without errors
- [ ] Replay attack protection works (same token can't be used twice)
- [ ] No CORS errors in browser console

---

## Rollback Plan

If issues occur:

```bash
# SSH into server
ssh root@47.80.66.95

# Revert to previous commit
cd /var/www/tms-server
git reset --hard HEAD~1

# Revert environment variables
nano .env
# Change JWT_EXPIRATION_HOURS back to 24
# Change ALLOWED_ORIGINS back to old value

# Restart
pm2 restart tms-server
```

---

## Success Criteria

✅ Deployment successful if:
1. 401 errors return as status 401 (not 500)  
2. Users can authenticate via SSO  
3. Conversations load without errors  
4. Same token cannot be used twice  
5. No CORS errors  

