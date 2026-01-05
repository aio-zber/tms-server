# TMS Deployment Credentials Checklist

## ✅ Credentials You Already Have

### ECS Instances
```
Staging:
  Public IP: 47.80.66.95
  Hostname: tms-chat-staging.hotelsogo-ai.com

Production:
  Public IP: 47.80.71.165
  Hostname: tms-chat.hotelsogo-ai.com
```

### RDS PostgreSQL
```
Host: pgm-5tsq1t17984pyydh0o.pgsql.ap-southeast-6.rds.aliyuncs.com
Port: 5432
Username: postgres
Password: Syxgim-zynciw-qibxe7

Databases:
  - tms_staging_db (for staging)
  - tms_production_db (for production)
```

### Tair Redis
```
Host: r-5tsm9aoc5soeozbq3v.redis.ap-southeast-6.rds.aliyuncs.com
Port: 6379
Password: gosgoj-9gygwo-Dusbob

Databases:
  - Database 1 (for staging)
  - Database 0 (for production)
```

### OSS Bucket Info
```
Bucket Name: tms-oss-goli
Region: ap-southeast-6
Public Endpoint: oss-ap-southeast-6.aliyuncs.com
Internal Endpoint: oss-ap-southeast-6-internal.aliyuncs.com (use this!)
```

### Application Secrets (From Railway)
```
JWT_SECRET: v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=
NEXTAUTH_SECRET: v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=
USER_MANAGEMENT_API_KEY: goh9oNDRy0Hs6O6CjnpI6ZiUMOT3xXnlhm+oFQvMamw=
```

### GCGC URLs
```
Staging: https://gcgc-team-management-system-staging.up.railway.app
Production: https://gcgc-team-management-system-production.up.railway.app (TBD)
```

---

## ❌ Credentials Still Needed

### OSS Access Keys (REQUIRED for file uploads)

**What**: Authentication credentials to upload/download files to OSS bucket

**Where to get**: Alibaba Cloud Console → RAM → Create AccessKey

**See**: `deployment/GET_OSS_CREDENTIALS.md` for step-by-step guide

```
OSS_ACCESS_KEY_ID: <NEED TO CREATE>
OSS_ACCESS_KEY_SECRET: <NEED TO CREATE>
```

**Options:**
1. **Create RAM user** (recommended - more secure)
   - Limited permissions
   - Easy to rotate/revoke

2. **Use root account AccessKey** (not recommended)
   - Full account access
   - Security risk

---

## 🔐 Where Each Credential Goes

### Backend (.env.staging / .env.production)

```bash
# Database - ✅ DONE
DATABASE_URL=postgresql+asyncpg://postgres:Syxgim-zynciw-qibxe7@pgm-5tsq1t17984pyydh0o.pgsql.ap-southeast-6.rds.aliyuncs.com:5432/tms_staging_db

# Redis - ✅ DONE
REDIS_URL=redis://:gosgoj-9gygwo-Dusbob@r-5tsm9aoc5soeozbq3v.redis.ap-southeast-6.rds.aliyuncs.com:6379/1
REDIS_PASSWORD=gosgoj-9gygwo-Dusbob

# GCGC - ✅ DONE
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
USER_MANAGEMENT_API_KEY=goh9oNDRy0Hs6O6CjnpI6ZiUMOT3xXnlhm+oFQvMamw=

# JWT - ✅ DONE
JWT_SECRET=v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=
NEXTAUTH_SECRET=v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=

# OSS - ❌ NEED ACCESS KEYS
OSS_ACCESS_KEY_ID=YOUR_OSS_ACCESS_KEY_ID_HERE
OSS_ACCESS_KEY_SECRET=YOUR_OSS_ACCESS_KEY_SECRET_HERE
OSS_BUCKET_NAME=tms-oss-goli
OSS_ENDPOINT=oss-ap-southeast-6-internal.aliyuncs.com
```

### Frontend (.env.production.local)

```bash
# API - ✅ DONE
NEXT_PUBLIC_API_URL=https://tms-chat-staging.hotelsogo-ai.com/api/v1

# GCGC - ✅ DONE
NEXT_PUBLIC_TEAM_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app
NEXT_PUBLIC_GCGC_LOGIN_URL=https://gcgc-team-management-system-staging.up.railway.app/auth/signin

# NextAuth - ✅ DONE
NEXTAUTH_SECRET=v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=
NEXTAUTH_URL=https://tms-chat-staging.hotelsogo-ai.com

# OSS - ✅ NOT NEEDED (backend handles uploads)
```

---

## 📋 Pre-Deployment Checklist

### Infrastructure ✅
- [x] ECS instances created
- [x] RDS PostgreSQL setup
- [x] Tair Redis setup
- [x] OSS bucket created

### Credentials ⚠️
- [x] Database credentials
- [x] Redis credentials
- [x] JWT secrets
- [x] GCGC API key
- [ ] **OSS Access Keys** ← NEED THIS

### DNS 🔲
- [ ] tms-chat-staging.hotelsogo-ai.com → 47.80.66.95
- [ ] tms-chat.hotelsogo-ai.com → 47.80.71.165

### Environment Files 🔲
- [ ] `.env.staging` created on server (copy from `.env.staging.example`)
- [ ] `.env.production` created on server (copy from `.env.production.example`)
- [ ] Frontend `.env.production.local` created on server
- [ ] OSS Access Keys added to all env files

---

## 🎯 Action Items

### 1. Get OSS Access Keys (5 minutes)
```bash
# Follow the guide:
cat deployment/GET_OSS_CREDENTIALS.md

# Or quick steps:
# 1. Login to Alibaba Cloud Console
# 2. Go to RAM → Users → Create User
# 3. Enable "Programmatic Access"
# 4. Grant "AliyunOSSFullAccess" permission
# 5. Save AccessKey ID and Secret (shown only once!)
```

### 2. Update Environment Files
```bash
# Edit .env.staging.example locally
nano .env.staging.example

# Update these lines:
OSS_ACCESS_KEY_ID=LTAI5t******************  # Your actual key
OSS_ACCESS_KEY_SECRET=3mK************************  # Your actual secret

# Repeat for .env.production.example
```

### 3. Deploy to Staging
```bash
# SSH to staging server
ssh root@47.80.66.95

# Follow Quick Start guide
cat /home/tmsapp/tms-server/deployment/QUICK_START.md
```

---

## 🔍 Verification

After deployment, verify each credential is working:

### Database
```bash
psql -h pgm-5tsq1t17984pyydh0o.pgsql.ap-southeast-6.rds.aliyuncs.com \
     -U postgres -d tms_staging_db
# Password: Syxgim-zynciw-qibxe7
```

### Redis
```bash
redis-cli -h r-5tsm9aoc5soeozbq3v.redis.ap-southeast-6.rds.aliyuncs.com \
          -p 6379 -a gosgoj-9gygwo-Dusbob
```

### OSS (After getting Access Keys)
```bash
# Install ossutil
wget http://gosspublic.alicdn.com/ossutil/1.7.16/ossutil64
chmod +x ossutil64

# Test access
./ossutil64 config
./ossutil64 ls
# Should show: oss://tms-oss-goli
```

### Application
```bash
# Backend health check
curl https://tms-chat-staging.hotelsogo-ai.com/health

# API health check
curl https://tms-chat-staging.hotelsogo-ai.com/api/v1/health

# Frontend
curl -I https://tms-chat-staging.hotelsogo-ai.com
```

---

## 🆘 Common Issues

### "AccessDenied" when uploading to OSS
**Cause**: RAM user doesn't have OSS permissions
**Fix**: Add `AliyunOSSFullAccess` policy to the RAM user

### "InvalidAccessKeyId"
**Cause**: Wrong OSS_ACCESS_KEY_ID or deleted key
**Fix**: Verify key in RAM console, create new if needed

### "Database connection refused"
**Cause**: Firewall blocking connection
**Fix**: Check RDS whitelist, add ECS internal IP

### "Redis connection timeout"
**Cause**: Wrong endpoint or firewall
**Fix**: Ensure using internal endpoint for same-region access

---

## 📞 Need Help?

1. **OSS Access Keys**: See `deployment/GET_OSS_CREDENTIALS.md`
2. **Deployment Steps**: See `deployment/QUICK_START.md`
3. **Migration Guide**: See `deployment/RAILWAY_TO_ALIBABA_MIGRATION.md`
4. **Summary**: See `deployment/DEPLOYMENT_SUMMARY.md`

---

## ✨ Ready to Deploy?

Once you have OSS Access Keys:

1. ✅ All infrastructure credentials available
2. ✅ Environment files configured
3. ✅ DNS records updated
4. ✅ Deployment guides ready

**Next step**: Follow `deployment/QUICK_START.md` 🚀
