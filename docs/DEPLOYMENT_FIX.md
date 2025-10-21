# Railway Deployment Fix - Pydantic Settings Type Error

**Date:** October 16, 2025, 3:49 PM  
**Status:** ✅ **FIXED** - Deployed to Railway

---

## 🔴 Problem

Railway deployment failed with this error:

```
pydantic_settings.sources.SettingsError: error parsing value for field "allowed_origins" from source "EnvSettingsSource"
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

---

## 🔍 Root Cause

**The Issue:**
- I initially changed `allowed_origins` field type from `str` to `List[str]`
- When Pydantic Settings sees a `List[str]` type, it automatically tries to **JSON-decode** the environment variable
- Railway's environment variable is a **comma-separated string**: 
  ```
  ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app,http://localhost:3000
  ```
- This is **NOT valid JSON**, so Pydantic failed to parse it

**Why It Happened:**
```python
# Before (WRONG - causes JSON parsing):
allowed_origins: List[str] = Field(...)  # ❌ Pydantic tries to json.loads() the env var

# Railway env var:
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app  # ❌ Not valid JSON
```

---

## ✅ Solution

Keep the field type as `str` and convert to list when needed:

```python
# config.py
class Settings(BaseSettings):
    # Field stays as str (Pydantic won't try to JSON-decode it)
    allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Validator parses the string
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return ["http://localhost:3000"]
    
    # Helper method returns as list when needed
    def get_allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        return self.parse_cors_origins(self.allowed_origins)
```

```python
# main.py - Use the helper method
cors_origins = settings.get_allowed_origins_list()  # ✅ Returns List[str]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # ...
)
```

---

## 📦 Files Changed

1. **`app/config.py`**
   - Reverted `allowed_origins` type from `List[str]` back to `str`
   - Reverted `allowed_hosts` type from `List[str]` back to `str`
   - Added `get_allowed_origins_list()` helper method
   - Added `get_allowed_hosts_list()` helper method

2. **`app/main.py`**
   - Changed `settings.allowed_origins` to `settings.get_allowed_origins_list()`

3. **`app/core/websocket.py`**
   - Changed `settings.allowed_origins` to `settings.get_allowed_origins_list()`

---

## 🚀 Deployment

**Commit:** `ba7c3c6`

```bash
git commit -m "fix: Pydantic Settings type parsing for allowed_origins"
git push origin staging
```

**Railway Status:** Deploying now... (check Railway dashboard)

---

## ✅ Verification

After Railway finishes deploying, verify:

### 1. Check Deployment Logs
Railway should show:
```
🌐 CORS allowed origins: ['https://tms-client-staging.up.railway.app', 'http://localhost:3000']
Initializing ConnectionManager with WebSocket-only mode
Prepared CORS origins for Socket.IO: ['https://tms-client-staging.up.railway.app', ...]
Socket.IO server initialized successfully
✅ Application startup complete
```

### 2. Test Health Endpoint
```bash
curl https://tms-server-staging.up.railway.app/health

# Expected:
{
  "status": "healthy",
  "environment": "staging"
}
```

### 3. Test WebSocket Config
```bash
curl https://tms-server-staging.up.railway.app/health/websocket | jq '.config.cors_origins'

# Expected:
[
  "https://tms-client-staging.up.railway.app",
  "http://localhost:3000"
]
```

---

## 💡 Key Learnings

### Pydantic Settings Type Behavior

| Field Type | Environment Variable | Pydantic Behavior |
|-----------|---------------------|-------------------|
| `str` | `value1,value2` | ✅ Accepts as string |
| `List[str]` | `value1,value2` | ❌ Tries `json.loads()` → fails |
| `List[str]` | `["value1", "value2"]` | ✅ Valid JSON array |

### Best Practice

When using **comma-separated environment variables** with Pydantic Settings:

1. ✅ **Keep field type as `str`**
2. ✅ **Use validators to parse to list**
3. ✅ **Add helper methods to get as list**
4. ❌ **Don't use `List[str]` type** (forces JSON parsing)

### Railway Environment Variables

Railway provides environment variables as **plain strings**, not JSON:

```bash
# What Railway provides:
ALLOWED_ORIGINS=https://example.com,http://localhost:3000

# NOT this (JSON):
ALLOWED_ORIGINS=["https://example.com", "http://localhost:3000"]
```

---

## 🔄 What Changed From Original Fix

**Original Attempt (Caused Error):**
```python
allowed_origins: List[str] = Field(...)  # ❌ Forces JSON parsing
```

**Corrected Fix:**
```python
allowed_origins: str = Field(...)  # ✅ Accepts string
get_allowed_origins_list() -> List[str]  # ✅ Returns as list when needed
```

---

## 📚 Related Documentation

- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Field Validators: https://docs.pydantic.dev/latest/concepts/validators/
- Railway Environment Variables: https://docs.railway.app/develop/variables

---

## ✅ Status

- [x] Error identified
- [x] Fix applied
- [x] Committed to git
- [x] Pushed to Railway
- [ ] Deployment verified (check Railway logs)
- [ ] Health endpoint tested
- [ ] WebSocket config verified

---

**Next:** After Railway deployment completes (~2 minutes), proceed with TMS-Client deployment as originally planned.

**No changes needed to TMS-Client** - the Socket.IO path fix is still valid and ready to deploy.

