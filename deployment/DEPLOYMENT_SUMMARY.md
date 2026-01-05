# TMS Alibaba Cloud Deployment Summary

## What You Have Now

### Current Setup (Railway)
- **TMS Server**: https://tms-server-staging.up.railway.app
- **TMS Client**: https://tms-client-staging.up.railway.app
- **Database**: Railway PostgreSQL (automatic)
- **Redis**: Railway Redis (automatic)
- **File Storage**: Cloudinary

### New Setup (Alibaba Cloud)
- **Both Server & Client**: Same ECS instance with Nginx
- **Staging**: https://tms-chat-staging.example.com (47.80.66.95)
- **Production**: https://tms-chat.example.com (47.80.71.165)
- **Database**: Alibaba Cloud RDS PostgreSQL ✅
- **Redis**: Alibaba Cloud Tair Redis ✅
- **File Storage**: Alibaba Cloud OSS (need credentials)

## Architecture on Alibaba Cloud

```
User Browser
    ↓
HTTPS (Port 443)
    ↓
Nginx (Reverse Proxy)
    ├─→ /api/*  → FastAPI Backend (localhost:8000)
    ├─→ /docs   → FastAPI Docs (localhost:8000)
    └─→ /*      → Next.js Frontend (localhost:3000)
         ↓
    Services
    ├─→ PostgreSQL RDS (REDACTED_RDS_HOST...)
    ├─→ Tair Redis (REDACTED_REDIS_HOST...)
    └─→ OSS (tms-oss-goli)
```

## Files Created for You

### Documentation
✅ `DEPLOYMENT_GUIDE.md` - Full deployment guide
✅ `deployment/QUICK_START.md` - Step-by-step quick start
✅ `deployment/README.md` - Deployment files overview
✅ `deployment/RAILWAY_TO_ALIBABA_MIGRATION.md` - Migration guide

### Configuration Files
✅ `deployment/nginx/tms-production.conf` - Nginx config (production)
✅ `deployment/nginx/tms-staging.conf` - Nginx config (staging)
✅ `deployment/systemd/tms-backend.service` - Backend service
✅ `deployment/systemd/tms-frontend.service` - Frontend service

### Scripts
✅ `deployment/scripts/deploy.sh` - Deployment automation
✅ `deployment/scripts/backup-db.sh` - Database backup
✅ `deployment/scripts/restore-db.sh` - Database restore

### Environment Files (Ready to use!)
✅ `.env.staging.example` - Backend staging (with your Railway values!)
✅ `.env.production.example` - Backend production
✅ `deployment/frontend.env.staging.alibaba` - Frontend staging (with your values!)
✅ `deployment/frontend.env.production.alibaba` - Frontend production

## What You Need To Do

### 1. Get OSS Credentials (Required for file uploads)

```bash
# Login to Alibaba Cloud Console
# Go to: OSS → AccessKey Management
# Create AccessKey
# Save these values:
- OSS_ACCESS_KEY_ID
- OSS_ACCESS_KEY_SECRET
```

### 2. Update Environment Files

Update these lines in `.env.staging.example`:
```bash
OSS_ACCESS_KEY_ID=your_actual_key_here
OSS_ACCESS_KEY_SECRET=your_actual_secret_here
```

### 3. Deploy to Staging First

Follow the **Quick Start Guide** at `deployment/QUICK_START.md`.

Key steps:
1. SSH to staging server: `ssh root@47.80.66.95`
2. Install dependencies
3. Clone repositories
4. Copy environment files
5. Install services
6. Configure Nginx
7. Setup SSL

### 4. Update DNS Records

Point your domains to Alibaba Cloud IPs:

```
Type: A
Name: tms-chat-staging.example.com
Value: 47.80.66.95

Type: A
Name: tms-chat.example.com
Value: 47.80.71.165
```

### 5. Migrate Files from Cloudinary to OSS (Optional)

If you have existing files in Cloudinary, you'll need to:
1. Download files from Cloudinary
2. Upload to OSS
3. Update database URLs

See `RAILWAY_TO_ALIBABA_MIGRATION.md` for details.

## Your Secrets (From Railway)

These are already configured in the environment examples:

```bash
# JWT Configuration (KEEP THESE EXACTLY THE SAME!)
JWT_SECRET=REDACTED_JWT_SECRET
NEXTAUTH_SECRET=REDACTED_JWT_SECRET

# GCGC API
USER_MANAGEMENT_API_KEY=REDACTED_API_KEY
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-staging.up.railway.app

# Alibaba Cloud Database (already configured)
Database: localhost
Redis: localhost
```

## Important Notes

### ⚠️ Critical Items

1. **JWT_SECRET must match** across:
   - TMS Server backend
   - TMS Client frontend
   - GCGC Team Management System

   ✅ Already configured correctly in your environment files!

2. **Database separation**:
   - Staging uses: `tms_staging_db`
   - Production uses: `tms_production_db`
   - Redis staging uses db 1, production uses db 0

3. **CORS Origins** updated to include:
   - Alibaba Cloud domains
   - Railway domains (for gradual migration)
   - Localhost (for testing)

### 📋 Pre-Deployment Checklist

- [ ] Got OSS credentials
- [ ] Updated environment files with OSS credentials
- [ ] DNS records pointing to Alibaba Cloud IPs
- [ ] SSH access to ECS instances works
- [ ] Read the Quick Start guide
- [ ] Backed up Railway database (just in case)

### 🚀 Deployment Order

1. **Deploy Staging First** (test everything)
   - Server: 47.80.66.95
   - Domain: tms-chat-staging.example.com

2. **Test Thoroughly**
   - Login/authentication
   - Send messages
   - Upload files (once OSS is configured)
   - WebSocket connections

3. **Deploy Production** (when staging works)
   - Server: 47.80.71.165
   - Domain: tms-chat.example.com

## Quick Command Reference

```bash
# SSH to servers
ssh root@47.80.66.95  # Staging
ssh root@47.80.71.165 # Production

# View logs
sudo journalctl -u tms-backend -f
sudo journalctl -u tms-frontend -f

# Restart services
sudo systemctl restart tms-backend tms-frontend nginx

# Deploy updates (after initial setup)
sudo su - tmsapp
cd /home/tmsapp/tms-server
./deployment/scripts/deploy.sh staging

# Backup database
./deployment/scripts/backup-db.sh staging
```

## Timeline Estimate

| Task | Time |
|------|------|
| Get OSS credentials | 10 minutes |
| Update environment files | 5 minutes |
| Initial server setup | 30 minutes |
| Deploy backend + frontend | 20 minutes |
| Configure Nginx + SSL | 15 minutes |
| DNS update + propagation | 5-60 minutes |
| Testing | 30 minutes |
| **Total** | **~2 hours** |

## What Happens After Deployment

### Immediate (0-24 hours)
- Monitor logs for errors
- Test all features thoroughly
- Keep Railway running as backup
- Monitor DNS propagation

### Short-term (1-7 days)
- Set up automated backups
- Configure monitoring/alerts
- Optimize performance
- Document any issues

### Long-term (1+ month)
- Decommission Railway
- Set up CI/CD pipeline
- Implement advanced features
- Cost optimization

## Support Resources

1. **Quick Start Guide**: `deployment/QUICK_START.md` ← Start here!
2. **Full Deployment Guide**: `DEPLOYMENT_GUIDE.md`
3. **Migration Guide**: `deployment/RAILWAY_TO_ALIBABA_MIGRATION.md`
4. **Backend Docs**: `CLAUDE.md`

## Questions to Clarify

Before you start, make sure you have answers to:

1. ✅ Do you have Alibaba Cloud OSS credentials?
   - If no: Create them in Alibaba Cloud Console → OSS → AccessKey

2. ✅ Are you deploying staging first?
   - Recommended: Yes, test on staging before production

3. ✅ Do you have SSH access to both ECS instances?
   - Test: `ssh root@47.80.66.95` and `ssh root@47.80.71.165`

4. ✅ Have you updated DNS records?
   - They can propagate while you set up the servers

5. ❓ Do you want to migrate existing Cloudinary files to OSS?
   - If yes: See migration guide
   - If no: New files will use OSS, old files stay on Cloudinary

## Next Step

🎯 **Start with**: `deployment/QUICK_START.md`

This guide will walk you through the entire deployment process step-by-step!

Good luck with your deployment! 🚀
