# Railway Configuration Instructions - URGENT FIX

## 🚨 CRITICAL: Authentication is Currently Broken

Your TMS-Server authentication is failing because of incorrect Railway environment variables.

### The Problem
1. `TMS_API_URL` points to the wrong service (TMS-Client frontend instead of GCGC backend)
2. `JWT_SECRET` doesn't match GCGC's `NEXTAUTH_SECRET`
3. Variable names are confusing (now renamed for clarity)

---

## ✅ Step-by-Step Fix Instructions

### Step 1: Access Railway Dashboard

1. Go to https://railway.app
2. Navigate to your **TMS-Server** project
3. Click on the **Variables** tab

---

### Step 2: Delete Old Variables

Delete these variables (they have wrong names):
- ❌ `TMS_API_URL`
- ❌ `TMS_API_KEY`
- ❌ `TMS_API_TIMEOUT`

---

### Step 3: Add New Variables with Correct Values

Add these new variables:

#### **USER_MANAGEMENT_API_URL**
```
https://gcgc-team-management-system-staging.up.railway.app
```
⚠️ **CRITICAL**: This MUST point to GCGC backend, NOT tms-client!

#### **USER_MANAGEMENT_API_KEY**
```
REDACTED_API_KEY
```
(Same value as old `TMS_API_KEY`)

#### **USER_MANAGEMENT_API_TIMEOUT** (optional)
```
30
```

---

### Step 4: Fix JWT Secret

Update this existing variable:

#### **JWT_SECRET**
```
REDACTED_JWT_SECRET
```
⚠️ **CRITICAL**: This MUST match GCGC's `NEXTAUTH_SECRET` exactly!

---

### Step 5: Verify Other Variables

Ensure these are correct:

#### **ENVIRONMENT**
```
staging
```

#### **DEBUG**
```
true
```

#### **DATABASE_URL**
```
${{Postgres.DATABASE_URL}}
```

#### **DATABASE_URL_SYNC**
```
${{Postgres.DATABASE_URL}}
```

#### **ALLOWED_ORIGINS**
```
https://tms-client-staging.up.railway.app
```

---

### Step 6: Fix TMS-Client URL (Bonus Fix)

While you're in Railway, also fix TMS-Client:

1. Go to **TMS-Client** project
2. Find `NEXT_PUBLIC_API_URL`
3. Change from:
   ```
   https://tms-server-staging.up.railway.app//api/v1
   ```
   To (remove double slash):
   ```
   https://tms-server-staging.up.railway.app/api/v1
   ```

---

### Step 7: Deploy

1. Click **Deploy** button in Railway dashboard
2. Wait for deployment to complete (~2-3 minutes)
3. Check logs for successful startup

---

## 🧪 Testing After Deployment

### Test 1: Health Check
```bash
curl https://tms-server-staging.up.railway.app/health
```
Expected: `{"status":"healthy","environment":"staging"}`

### Test 2: Readiness Check
```bash
curl https://tms-server-staging.up.railway.app/health/ready
```
Expected:
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

⚠️ If `gcgc_user_management: false`, GCGC is down or URL is wrong!

### Test 3: Login Flow

1. Go to TMS-Client: https://tms-client-staging.up.railway.app
2. Login with: `zms@gmail.com` / `password`
3. You should be redirected to chat view
4. No errors in browser console

---

## 📋 Complete Variable Checklist

After making changes, verify you have ALL these variables in TMS-Server:

- [ ] `DATABASE_URL`
- [ ] `DATABASE_URL_SYNC`
- [ ] `USER_MANAGEMENT_API_URL` (NEW NAME - points to GCGC)
- [ ] `USER_MANAGEMENT_API_KEY` (NEW NAME)
- [ ] `USER_MANAGEMENT_API_TIMEOUT` (optional, NEW NAME)
- [ ] `JWT_SECRET` (updated value to match GCGC)
- [ ] `ALLOWED_ORIGINS`
- [ ] `ENVIRONMENT`
- [ ] `DEBUG`
- [ ] `REDIS_URL` (optional - can be empty)

---

## 🆘 Troubleshooting

### Issue: "USER_MANAGEMENT_API_URL not found"
**Fix**: You forgot to add the new variable. Go back to Step 3.

### Issue: "Invalid or expired token"
**Fix**: `JWT_SECRET` doesn't match GCGC's `NEXTAUTH_SECRET`. Double-check Step 4.

### Issue: Health check shows `gcgc_user_management: false`
**Possible causes**:
1. GCGC service is down - check GCGC Railway logs
2. URL is wrong - verify `USER_MANAGEMENT_API_URL` exactly matches:
   ```
   https://gcgc-team-management-system-staging.up.railway.app
   ```
   (No trailing slash!)

### Issue: Still getting authentication errors
1. Check Railway logs for specific error messages
2. Verify all variables are set correctly (use checklist above)
3. Try restarting the Railway service
4. Clear browser cache and try login again

---

## 📊 Summary of Changes

| What Changed | Old Value | New Value |
|--------------|-----------|-----------|
| Variable name | `TMS_API_URL` | `USER_MANAGEMENT_API_URL` |
| API URL | `https://tms-client-staging.up.railway.app` ❌ | `https://gcgc-team-management-system-staging.up.railway.app` ✅ |
| Variable name | `TMS_API_KEY` | `USER_MANAGEMENT_API_KEY` |
| JWT Secret | `REDACTED_JWT_SECRET` ❌ | `REDACTED_JWT_SECRET` ✅ |

---

## ⏰ Estimated Time

- Variable updates: 5 minutes
- Deployment: 3 minutes
- Testing: 2 minutes
- **Total: ~10 minutes**

---

## 📞 Need Help?

If you're stuck after following these instructions:
1. Check Railway deployment logs for errors
2. Review `MIGRATION_AUTH_FIX.md` for detailed explanation
3. Contact the development team with:
   - Screenshot of Railway variables
   - Railway deployment logs
   - Error messages from browser console

---

## ✅ Success Criteria

You'll know it's fixed when:
- [ ] `/health/ready` shows `gcgc_user_management: true`
- [ ] Login works without errors
- [ ] User is redirected to chat view after login
- [ ] Can send messages successfully
- [ ] No authentication errors in logs

---

**Last Updated:** 2025-10-14
**Status:** Ready to deploy
**Priority:** URGENT - Fixes authentication
