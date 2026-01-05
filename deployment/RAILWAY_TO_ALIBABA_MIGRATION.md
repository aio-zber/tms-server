# Railway to Alibaba Cloud Migration Guide

This guide helps you migrate your TMS application from Railway to Alibaba Cloud ECS.

## Key Differences

### Infrastructure

| Aspect | Railway | Alibaba Cloud |
|--------|---------|---------------|
| **Application Hosting** | Automatic containers | ECS instances (self-managed VMs) |
| **Database** | Railway PostgreSQL | Alibaba Cloud RDS PostgreSQL |
| **Redis** | Railway Redis | Alibaba Cloud Tair Redis |
| **File Storage** | Cloudinary | Alibaba Cloud OSS |
| **SSL/HTTPS** | Automatic | Manual (Let's Encrypt/Certbot) |
| **Deployments** | Git push triggers deploy | Manual or scripted deploy |
| **Environment Variables** | Railway dashboard | `.env` files on server |
| **Reverse Proxy** | Built-in | Nginx (self-configured) |

### Environment Variable Changes

#### Variables That Stay the Same

These work exactly the same on both platforms:

```bash
✅ ENVIRONMENT
✅ DEBUG
✅ USER_MANAGEMENT_API_URL
✅ USER_MANAGEMENT_API_KEY
✅ USER_MANAGEMENT_API_TIMEOUT
✅ JWT_SECRET
✅ NEXTAUTH_SECRET
✅ GCGC_LOGIN_URL
```

#### Variables That Need Updates

**1. Database URLs** - Replace Railway interpolation with actual Alibaba RDS URLs:

```bash
# Railway (automatic)
DATABASE_URL="${{Postgres.DATABASE_URL}}"

# Alibaba Cloud (explicit)
DATABASE_URL=postgresql+asyncpg://postgres:REDACTED_DB_PASSWORD@localhost:5432/tms_staging_db
```

**2. Redis URLs** - Replace Railway interpolation with Alibaba Redis URLs:

```bash
# Railway (automatic)
REDIS_URL="${{Redis.REDIS_URL}}"
REDIS_PASSWORD="${{Redis.REDIS_PASSWORD}}"

# Alibaba Cloud (explicit)
REDIS_URL=redis://:REDACTED_REDIS_PASSWORD@localhost:6379/1
REDIS_PASSWORD=REDACTED_REDIS_PASSWORD
```

**3. CORS Origins** - Update to include Alibaba domains:

```bash
# Railway
ALLOWED_ORIGINS=https://tms-client-staging.up.railway.app

# Alibaba Cloud
ALLOWED_ORIGINS=https://tms-chat-staging.example.com,http://localhost:3000
```

#### Variables to Add (Alibaba Cloud Only)

**OSS Configuration** - Replace Cloudinary:

```bash
# Remove (Cloudinary - Railway)
NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME=your-cloud-name
NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET=your-upload-preset

# Add (OSS - Alibaba Cloud)
OSS_ACCESS_KEY_ID=your_oss_access_key_id
OSS_ACCESS_KEY_SECRET=your_oss_access_key_secret
OSS_BUCKET_NAME=tms-oss-goli
OSS_ENDPOINT=oss-ap-southeast-6.aliyuncs.com
```

#### Frontend API URLs

**Railway** - Separate deployments, full URLs:
```bash
NEXT_PUBLIC_API_URL=https://tms-server-staging.up.railway.app/api/v1
```

**Alibaba Cloud** - Same domain, Nginx routing:
```bash
NEXT_PUBLIC_API_URL=https://tms-chat-staging.example.com/api/v1
```

## Migration Steps

### Phase 1: Preparation (While Railway is still running)

1. **Set up Alibaba Cloud resources** (Already done ✅)
   - ECS instances
   - RDS PostgreSQL
   - Tair Redis
   - OSS bucket

2. **Get OSS credentials**
   - Log in to Alibaba Cloud Console
   - Navigate to OSS
   - Create Access Key (if not already created)
   - Save `OSS_ACCESS_KEY_ID` and `OSS_ACCESS_KEY_SECRET`

3. **Update DNS records** (prepare but don't switch yet)
   - Add A records pointing to Alibaba Cloud IPs
   - Keep TTL low (300s) for quick switching

4. **Test database connectivity**
   ```bash
   psql -h localhost \
        -U postgres -d tms_staging_db
   ```

### Phase 2: Deploy to Alibaba Cloud (Parallel to Railway)

1. **Follow the Quick Start guide**
   - See: `deployment/QUICK_START.md`

2. **Configure staging environment first**
   - Deploy to staging ECS instance
   - Test thoroughly before production

3. **Migrate data if needed**
   ```bash
   # Export from Railway PostgreSQL
   pg_dump -h railway-postgres-url -U postgres -d railway_db > backup.sql

   # Import to Alibaba Cloud RDS
   psql -h localhost \
        -U postgres -d tms_staging_db < backup.sql
   ```

4. **Migrate files from Cloudinary to OSS** (if needed)
   - Download existing files from Cloudinary
   - Upload to Alibaba Cloud OSS
   - Update database URLs to point to OSS

### Phase 3: Switch Over

1. **Test everything on Alibaba Cloud**
   - Access via IP or temporary domain
   - Test all features: messaging, file uploads, auth, etc.

2. **Update DNS records**
   - Point domains to Alibaba Cloud IPs
   - Wait for DNS propagation (can take up to 48h, but usually 5-30 minutes)

3. **Monitor both platforms**
   - Keep Railway running for 24-48 hours as backup
   - Monitor Alibaba Cloud logs and metrics

4. **Decommission Railway** (after confirmation)
   - Download any final backups
   - Cancel Railway services

## File Upload Migration: Cloudinary → OSS

Your TMS client currently uses Cloudinary for file uploads. With Alibaba Cloud, you'll use OSS instead.

### Backend Changes Required

You'll need to implement OSS upload endpoints in your FastAPI backend:

```python
# app/api/v1/files.py (create this if it doesn't exist)
from fastapi import APIRouter, UploadFile, HTTPException
from app.core.oss_client import generate_upload_url, upload_file

router = APIRouter()

@router.post("/upload-url")
async def get_upload_url(filename: str, content_type: str):
    """Generate a signed URL for direct upload to OSS"""
    try:
        file_key = f"uploads/{filename}"
        url = generate_upload_url(file_key)
        return {"upload_url": url, "file_key": file_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_file_direct(file: UploadFile):
    """Direct file upload to OSS via backend"""
    try:
        file_key = await upload_file(file)
        download_url = generate_download_url(file_key)
        return {"file_key": file_key, "url": download_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Frontend Changes Required

Update your file upload component to use the backend API instead of Cloudinary:

```typescript
// Before (Cloudinary)
const uploadToCloudinary = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('upload_preset', process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET);

  const response = await fetch(
    `https://api.cloudinary.com/v1_1/${process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME}/upload`,
    { method: 'POST', body: formData }
  );
  return response.json();
};

// After (OSS via backend)
const uploadToOSS = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/files/upload`,
    {
      method: 'POST',
      body: formData,
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    }
  );
  return response.json();
};
```

## Environment Files Checklist

### Backend (tms-server)

- [ ] Copy `.env.staging.example` to `.env.staging`
- [ ] Update `OSS_ACCESS_KEY_ID`
- [ ] Update `OSS_ACCESS_KEY_SECRET`
- [ ] Verify all database and Redis URLs
- [ ] Keep same `JWT_SECRET` and `NEXTAUTH_SECRET`

### Frontend (tms-client)

- [ ] Copy `deployment/frontend.env.staging.alibaba` to `.env.production.local`
- [ ] Update `NEXT_PUBLIC_API_URL` to Alibaba domain
- [ ] Update `NEXTAUTH_URL` to Alibaba domain
- [ ] Remove Cloudinary variables
- [ ] Keep same `NEXTAUTH_SECRET`

## Testing Checklist

Test these features after deployment:

- [ ] User authentication (login/logout)
- [ ] Sending messages
- [ ] File uploads (images, documents)
- [ ] Voice/video calls
- [ ] Polls
- [ ] WebSocket connections (real-time messaging)
- [ ] Conversation creation
- [ ] User search
- [ ] Notifications

## Rollback Plan

If something goes wrong:

1. **DNS rollback** (fastest)
   ```bash
   # Point DNS back to Railway IPs
   # TTL should be low (300s) for quick propagation
   ```

2. **Database rollback** (if needed)
   ```bash
   # Restore from backup
   ./deployment/scripts/restore-db.sh /path/to/backup.sql.gz staging
   ```

3. **Keep Railway running** for at least 24-48 hours after DNS switch

## Cost Comparison

### Railway (Current)

- **Hobby Plan**: ~$5-20/month (for small apps)
- **Pro Plan**: ~$20-100+/month (for production apps)
- Includes: Database, Redis, hosting, SSL, deployments

### Alibaba Cloud (New)

**Monthly estimate for staging + production:**

| Service | Cost (USD/month) |
|---------|------------------|
| 2x ECS instances (2 vCPU, 4GB RAM) | ~$30-40 |
| RDS PostgreSQL (2 vCPU, 4GB RAM) | ~$40-60 |
| Tair Redis (1GB) | ~$10-15 |
| OSS (100GB storage + traffic) | ~$5-10 |
| Bandwidth (100GB/month) | ~$10-15 |
| **Total** | **~$95-140/month** |

**Notes:**
- Alibaba Cloud costs scale with usage
- Use Reserved Instances for 30-50% discount
- Internal traffic between services in same region is free
- More control and customization than Railway

## Support & Troubleshooting

- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Quick Start**: `deployment/QUICK_START.md`
- **Backend Docs**: `CLAUDE.md`

## Next Steps After Migration

1. **Set up monitoring**
   - Alibaba Cloud CloudMonitor
   - Custom logging and alerting

2. **Configure backups**
   - Daily database backups (already configured)
   - Weekly full backups to OSS

3. **Set up CI/CD**
   - GitHub Actions for automated deployment
   - Or use Alibaba Cloud DevOps

4. **Performance optimization**
   - Enable OSS CDN for faster file access
   - Configure Redis caching strategy
   - Optimize database queries

5. **Security hardening**
   - Regular security updates
   - Firewall configuration
   - Intrusion detection
