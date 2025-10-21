# Authentication Fix Migration Guide

**Date:** 2025-10-14
**Breaking Change:** Environment variable names changed
**Impact:** HIGH - Requires Railway configuration updates

---

## What Changed?

We renamed environment variables to clarify that they point to the GCGC Team Management System (user management), not the TMS messaging system itself.

### Variable Name Changes

| Old Name | New Name | Purpose |
|----------|----------|---------|
| `TMS_API_URL` | `USER_MANAGEMENT_API_URL` | URL to GCGC Team Management System API |
| `TMS_API_KEY` | `USER_MANAGEMENT_API_KEY` | API key for GCGC authentication |
| `TMS_API_TIMEOUT` | `USER_MANAGEMENT_API_TIMEOUT` | Request timeout for GCGC API calls |

---

## Why This Change?

**The Problem:**
- Variable name `TMS_API_URL` was confusing because:
  - The messaging system is called "TMS" (Team Messaging System)
  - But the variable pointed to GCGC (user management system), not the messaging API
  - Developers thought it should point to the TMS-Server itself (wrong!)

**The Solution:**
- Renamed to `USER_MANAGEMENT_API_URL` to clearly indicate it points to GCGC
- This eliminates confusion about which service the variable references

---

## Migration Steps

### 1. Update Railway Environment Variables (TMS-Server)

#### ⚠️ CRITICAL: Update These Variables

```bash
# OLD CONFIGURATION (WRONG VALUES):
TMS_API_URL="https://tms-client-staging.up.railway.app"  # ❌ This was pointing to frontend!
TMS_API_KEY="REDACTED_API_KEY"
TMS_API_TIMEOUT="30"
JWT_SECRET="REDACTED_JWT_SECRET"  # ❌ Didn't match GCGC!

# NEW CONFIGURATION (CORRECT VALUES):
USER_MANAGEMENT_API_URL="https://gcgc-team-management-system-staging.up.railway.app"  # ✅ Points to GCGC!
USER_MANAGEMENT_API_KEY="REDACTED_API_KEY"  # ✅ API key for GCGC
USER_MANAGEMENT_API_TIMEOUT="30"
JWT_SECRET="REDACTED_JWT_SECRET"  # ✅ Matches GCGC's NEXTAUTH_SECRET!
```

#### How to Update in Railway Dashboard:

1. Go to Railway dashboard → TMS-Server project
2. Navigate to **Variables** tab
3. **Delete old variables:**
   - Remove `TMS_API_URL`
   - Remove `TMS_API_KEY`
   - Remove `TMS_API_TIMEOUT` (optional, has default)
4. **Add new variables:**
   - Add `USER_MANAGEMENT_API_URL` = `https://gcgc-team-management-system-staging.up.railway.app`
   - Add `USER_MANAGEMENT_API_KEY` = `REDACTED_API_KEY`
   - Add `USER_MANAGEMENT_API_TIMEOUT` = `30` (optional)
5. **Update JWT secret:**
   - Update `JWT_SECRET` = `REDACTED_JWT_SECRET`
6. Click **Deploy** to restart with new configuration

---

### 2. Fix TMS-Client URL (Double Slash Issue)

While you're in Railway, also fix this issue in TMS-Client:

```bash
# BEFORE (has double slash //):
NEXT_PUBLIC_API_URL="https://tms-server-staging.up.railway.app//api/v1"

# AFTER (single slash):
NEXT_PUBLIC_API_URL="https://tms-server-staging.up.railway.app/api/v1"
```

---

### 3. Update Local Development `.env` File

If you're running TMS-Server locally, update your `.env` file:

```bash
# Replace these lines:
TMS_API_URL=...
TMS_API_KEY=...
TMS_API_TIMEOUT=...

# With these:
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
USER_MANAGEMENT_API_KEY=REDACTED_API_KEY
USER_MANAGEMENT_API_TIMEOUT=30

# And ensure JWT_SECRET matches GCGC:
JWT_SECRET=REDACTED_JWT_SECRET
```

---

## Testing After Migration

### 1. Check TMS-Server Health

```bash
# Test basic health (should return 200):
curl https://tms-server-staging.up.railway.app/health

# Test readiness (should show gcgc_user_management: true):
curl https://tms-server-staging.up.railway.app/health/ready
```

Expected response:
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

### 2. Test Authentication Flow

1. Login to TMS-Client using GCGC credentials (zms@gmail.com / password)
2. After successful login, you should be redirected to chat view
3. Check browser console for any errors
4. Try sending a test message

### 3. Monitor Railway Logs

Watch the TMS-Server logs for:
- ✅ Successful connection to GCGC
- ✅ Successful token validation
- ✅ User data synced from GCGC
- ❌ Any errors mentioning "TMS_API_URL" (should not exist)

---

## Rollback Plan

If something goes wrong, you can quickly rollback:

1. In Railway dashboard, revert to previous deployment
2. Or, restore old environment variables temporarily:
   ```bash
   TMS_API_URL="https://tms-client-staging.up.railway.app"
   TMS_API_KEY="REDACTED_API_KEY"
   JWT_SECRET="REDACTED_JWT_SECRET"
   ```
3. Note: This will restore the bug, but service will be running

---

## Common Issues

### Issue 1: "USER_MANAGEMENT_API_URL not found"
**Cause:** Forgot to add new environment variable
**Fix:** Add `USER_MANAGEMENT_API_URL` in Railway dashboard

### Issue 2: "Invalid or expired token"
**Cause:** `JWT_SECRET` doesn't match GCGC's `NEXTAUTH_SECRET`
**Fix:** Ensure `JWT_SECRET=REDACTED_JWT_SECRET`

### Issue 3: "TMS API unavailable"
**Cause:** `USER_MANAGEMENT_API_URL` pointing to wrong URL
**Fix:** Ensure URL is `https://gcgc-team-management-system-staging.up.railway.app` (no trailing slash)

### Issue 4: Health check shows `gcgc_user_management: false`
**Cause:** GCGC service is down or URL is wrong
**Fix:**
1. Check GCGC is running: `curl https://gcgc-team-management-system-staging.up.railway.app/health`
2. Verify URL in `USER_MANAGEMENT_API_URL` is correct

---

## FAQ

**Q: Why did `TMS_API_URL` point to the wrong service?**
A: It was a configuration error. The variable name was confusing, and someone set it to the TMS-Client frontend URL instead of the GCGC backend URL.

**Q: Can I keep the old variable names?**
A: No, the code now expects the new variable names. You must update Railway configuration.

**Q: Will this affect production?**
A: Only if you're using the same codebase for production. Update production variables accordingly.

**Q: Do I need to run database migrations?**
A: No, this change only affects environment variables and code, not the database schema.

**Q: What if I use a different Team Management System (not GCGC)?**
A: The variable names are now generic (`USER_MANAGEMENT_API_URL`), so they work with any user management system. Just point the URL to your system's API.

---

## Support

If you encounter issues after migration:
1. Check Railway logs for specific error messages
2. Verify all environment variables are set correctly
3. Test GCGC health endpoint directly
4. Contact the development team with logs

---

## Summary Checklist

- [ ] Updated `USER_MANAGEMENT_API_URL` to point to GCGC
- [ ] Updated `USER_MANAGEMENT_API_KEY` (same value as before)
- [ ] Removed old `TMS_API_*` variables from Railway
- [ ] Updated `JWT_SECRET` to match GCGC's `NEXTAUTH_SECRET`
- [ ] Fixed `NEXT_PUBLIC_API_URL` double slash in TMS-Client
- [ ] Deployed TMS-Server with new configuration
- [ ] Tested `/health` and `/health/ready` endpoints
- [ ] Tested login flow from TMS-Client
- [ ] Verified chat functionality works

**Migration Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Completed
