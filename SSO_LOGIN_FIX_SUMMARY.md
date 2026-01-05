# SSO Login Fix Summary

## Issues Fixed

### 1. ✅ Database Timezone Error (500 Error) - RESOLVED
**Problem:** Users table had `TIMESTAMP WITHOUT TIME ZONE` columns but Python code sent timezone-aware datetimes.

**Error Message:**
```
can't subtract offset-naive and offset-aware datetimes
$20::TIMESTAMP WITHOUT TIME ZONE
```

**Root Cause:** Migration file converted messages, conversations, etc. to TIMESTAMPTZ but **forgot the users table**.

**Fix Applied:**
- Updated migration to include users table conversion
- Created force migration script (`scripts/force_users_migration.py`)
- Migration successfully ran and converted users table to TIMESTAMPTZ

**Commits:**
- `67d6138` - Add users table to TIMESTAMPTZ migration
- `943afbb` - Add force migration script
- `bf02565` - Run force migration before server start

---

### 2. ✅ GCGC API Authentication Error (503 Error) - RESOLVED
**Problem:** TMS-Server was sending NextAuth session tokens as **Bearer tokens**, but GCGC expects them as **cookies**.

**Error Message:**
```json
{
  "error": "sso_authentication_failed",
  "message": "Session expired or invalid - redirected to login"
}
```

**Root Cause Investigation:**
1. GCGC API returned HTTP 307 redirect to `/auth/signin?callbackUrl=%2Fhealth`
2. TMS-Server was calling:
   ```python
   # ❌ WRONG: Sending session token as Bearer token
   headers["Authorization"] = f"Bearer {session_token}"
   response = await client.get(f"{base_url}/api/v1/users/me", headers=headers)
   ```
3. GCGC's NextAuth doesn't recognize session tokens in Authorization header
4. NextAuth expects session tokens in **cookies** with name `next-auth.session-token`

**Fix Applied:**
Changed `app/core/tms_client.py:get_current_user_from_session()` to send session token as cookies:

```python
# ✅ CORRECT: Send session token as cookie
cookies = {
    "next-auth.session-token": session_token,
    "__Secure-next-auth.session-token": session_token,  # Production HTTPS
    "__Host-next-auth.session-token": session_token     # Production HTTPS + path
}
response = await client.get(f"{base_url}/api/v1/users/me", cookies=cookies)
```

**Commit:**
- `850aa18` - Send NextAuth session token as cookie instead of Bearer token

---

### 3. ✅ Frontend Callback Endpoint (ALSO FIXED PREVIOUSLY)
**Problem:** Frontend was calling wrong auth endpoint and using wrong field names.

**Fix Applied (Previous Commit):**
- Changed endpoint from `/api/v1/auth/login` to `/api/v1/auth/login/sso`
- Send token via `X-GCGC-Session-Token` header
- Fixed field name: `tms_user_id` → `tmsUserId` (camelCase)

**Commit:**
- `dd3942a` - Update SSO callback to use correct endpoint and field names

---

## Architecture Flow (Now Correct)

```
┌─────────────┐
│ GCGC Login  │
│   Page      │
└──────┬──────┘
       │ User logs in
       │
       ▼
┌─────────────┐
│ GCGC sets   │
│ NextAuth    │ Set-Cookie: next-auth.session-token=XXXXX
│ cookie      │
└──────┬──────┘
       │
       │ Redirect to: /auth/callback?gcgc_token=XXXXX
       ▼
┌──────────────────────────────────────────────────────┐
│ TMS-Client Frontend                                  │
│ /auth/callback/page.tsx                             │
├──────────────────────────────────────────────────────┤
│ 1. Extract gcgc_token from URL                       │
│ 2. POST to /api/v1/auth/login/sso                    │
│    Header: X-GCGC-Session-Token: <gcgc_token>        │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ TMS-Server Backend                                   │
│ /api/v1/auth.py:sso_login()                         │
├──────────────────────────────────────────────────────┤
│ 1. Extract session token from header                 │
│ 2. Call tms_client.get_current_user_from_session()  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ TMS Client (app/core/tms_client.py)                 │
│ get_current_user_from_session()                     │
├──────────────────────────────────────────────────────┤
│ ✅ NEW: Send session token as cookies               │
│                                                      │
│ GET /api/v1/users/me                                │
│ Cookie: next-auth.session-token=<session_token>     │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ GCGC API                                            │
│ /api/v1/users/me                                    │
├──────────────────────────────────────────────────────┤
│ ✅ Validates NextAuth session cookie                │
│ ✅ Returns user data                                │
│                                                      │
│ Response:                                            │
│ {                                                    │
│   "id": "user-123",                                 │
│   "tmsUserId": "user-123",                          │
│   "email": "user@example.com",                      │
│   ...                                                │
│ }                                                    │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ TMS-Server                                          │
│ - Sync user to database (TIMESTAMPTZ columns work!) │
│ - Return JWT token to frontend                      │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ TMS-Client                                          │
│ - Store JWT token                                   │
│ - Store user ID (camelCase: tmsUserId)              │
│ - Redirect to /chats                                │
└──────────────────────────────────────────────────────┘
```

---

## What Changed

### Backend (tms-server)
1. **Migration**: Users table columns converted to TIMESTAMPTZ
2. **TMS Client**: Session tokens now sent as cookies instead of Bearer token
3. **Force Migration Script**: Ensures migration runs on deployment

### Frontend (tms-client)
1. **Callback Page**: Uses correct SSO endpoint
2. **Field Naming**: Uses camelCase (tmsUserId) consistently

---

## Testing Instructions

### Step 1: Clear Browser Data
```bash
# Clear localStorage, sessionStorage, and cookies for TMS-Client domain
# In browser DevTools Console:
localStorage.clear();
sessionStorage.clear();
# Then manually clear cookies for tms-client-staging.up.railway.app
```

### Step 2: Test SSO Login
1. Go to: https://tms-client-staging.up.railway.app
2. Should redirect to GCGC login
3. Log in with valid GCGC credentials
4. Should redirect to `/auth/callback?gcgc_token=...`
5. **Expected:** Successful login, redirect to `/chats`
6. **Check console for errors**

### Step 3: Verify Database
```sql
-- Check users table schema (should be TIMESTAMPTZ)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('last_synced_at', 'created_at', 'updated_at');

-- Expected: All three should show "timestamp with time zone"
```

### Step 4: Check Logs
```bash
# Backend logs should show:
✅ SSO Callback: GCGC session valid for user <user-id>
✅ Migration successful!

# Frontend console should show:
✅ SSO Callback: TMS token received
✅ SSO Callback: User ID stored: <user-id>
```

---

## Verification Checklist

- [ ] No 500 database errors in logs
- [ ] No 503 GCGC API errors in logs
- [ ] Users can successfully log in via SSO
- [ ] User data is stored with camelCase field names
- [ ] Conversations and messages load correctly
- [ ] No console errors during authentication
- [ ] Database users table has TIMESTAMPTZ columns

---

## Deployment Status

**Latest Commits:**
1. `850aa18` - Fix: Send NextAuth session token as cookie (LIVE)
2. `bf02565` - Fix: Run force migration before server start (LIVE)
3. `dd3942a` - Fix: Update SSO callback endpoint and field names (LIVE)
4. `943afbb` - Feat: Add force migration script (LIVE)
5. `67d6138` - Fix: Add users table to TIMESTAMPTZ migration (LIVE)

**Deployment:**
- Railway auto-deploys on push to staging branch
- Server health check: https://tms-server-staging.up.railway.app/health
- Status: ✅ Healthy

---

## Common Issues and Solutions

### Issue: "Still getting 503 error"
**Solution:**
1. Clear browser cookies and localStorage
2. Ensure GCGC is running at: https://gcgc-team-management-system-staging.up.railway.app
3. Check GCGC health: `curl https://gcgc-team-management-system-staging.up.railway.app/health`
4. Verify Railway environment variable `USER_MANAGEMENT_API_URL` is correct

### Issue: "500 database error"
**Solution:**
1. Check Railway deployment logs for migration output
2. Verify users table columns are TIMESTAMPTZ (see Step 3 above)
3. If still TIMESTAMP, manually run migration: `railway run alembic upgrade head`

### Issue: "User data not found"
**Solution:**
1. Check frontend console for field name errors
2. Verify using camelCase: `tmsUserId` not `tms_user_id`
3. Clear localStorage and re-login

---

## Technical Details

### Why Session Tokens Need to be Sent as Cookies

**NextAuth Session Flow:**
1. User logs into GCGC
2. NextAuth creates session in database
3. NextAuth sets cookie: `next-auth.session-token=<encrypted-token>`
4. Browser sends this cookie with subsequent requests
5. NextAuth middleware validates cookie against database session

**When sent as Bearer token:**
- NextAuth middleware doesn't check Authorization header for sessions
- Only checks cookies
- Results in 307 redirect to `/auth/signin`

**When sent as cookie:**
- NextAuth middleware finds and validates session
- Returns user data
- ✅ Authentication succeeds

### Why TIMESTAMPTZ Matters

**PostgreSQL Behavior:**
- `TIMESTAMP`: Stores naive datetime (no timezone info)
- `TIMESTAMPTZ`: Stores UTC and converts to client timezone on read

**Python asyncpg:**
- Sends timezone-aware `datetime` objects by default when using `utc_now()`
- Fails when column expects naive `TIMESTAMP`
- Works perfectly with `TIMESTAMPTZ`

**Migration Fix:**
```sql
ALTER TABLE users
  ALTER COLUMN last_synced_at TYPE TIMESTAMPTZ USING last_synced_at AT TIME ZONE 'UTC',
  ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
  ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
```

---

## References

- **Messenger/Telegram Pattern**: Session-based auth with timezone-aware timestamps
- **NextAuth Docs**: https://next-auth.js.org/configuration/options#cookies
- **PostgreSQL TIMESTAMPTZ**: https://www.postgresql.org/docs/current/datatype-datetime.html
- **Railway Deployment**: https://docs.railway.app/deploy/deployments

---

## Support

If issues persist after following this guide:
1. Check Railway deployment logs: `railway logs`
2. Check browser console for errors
3. Verify GCGC is running and accessible
4. Review commit history for any reverted changes
