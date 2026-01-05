# TMS Deployment Files

This directory contains all the configuration files and scripts needed to deploy TMS Server and Client on Alibaba Cloud ECS.

## Directory Structure

```
deployment/
├── README.md                           # This file
├── QUICK_START.md                      # Quick deployment guide
│
├── nginx/                              # Nginx configuration files
│   ├── tms-production.conf             # Production nginx config
│   └── tms-staging.conf                # Staging nginx config
│
├── systemd/                            # Systemd service files
│   ├── tms-backend.service             # Backend service definition
│   └── tms-frontend.service            # Frontend service definition
│
├── scripts/                            # Deployment and maintenance scripts
│   ├── deploy.sh                       # Main deployment script
│   ├── backup-db.sh                    # Database backup script
│   └── restore-db.sh                   # Database restore script
│
├── .env.production.template            # Backend production env template
├── .env.staging.template               # Backend staging env template
├── frontend-env.production.template    # Frontend production env template
└── frontend-env.staging.template       # Frontend staging env template
```

## Quick Links

- **[Quick Start Guide](QUICK_START.md)** - Fast deployment instructions
- **[Full Deployment Guide](../DEPLOYMENT_GUIDE.md)** - Comprehensive deployment documentation

## Files Overview

### Nginx Configuration

**`nginx/tms-production.conf`**
- Nginx reverse proxy configuration for production
- Routes `/api/*` to FastAPI backend (port 8000)
- Routes all other requests to Next.js frontend (port 3000)
- Includes SSL configuration, rate limiting, caching rules
- Copy to: `/etc/nginx/sites-available/tms-production`

**`nginx/tms-staging.conf`**
- Same as production but for staging environment
- Includes API documentation endpoints (`/docs`, `/redoc`)
- Copy to: `/etc/nginx/sites-available/tms-staging`

### Systemd Services

**`systemd/tms-backend.service`**
- Systemd service for FastAPI backend
- Runs uvicorn with 4 workers
- Auto-restart on failure
- Copy to: `/etc/systemd/system/tms-backend.service`

**`systemd/tms-frontend.service`**
- Systemd service for Next.js frontend
- Runs production Next.js server
- Auto-restart on failure
- Copy to: `/etc/systemd/system/tms-frontend.service`

### Deployment Scripts

**`scripts/deploy.sh`**
- Main deployment script for updates
- Pulls latest code, installs dependencies, runs migrations
- Restarts services and performs health checks
- Usage: `./deploy.sh [staging|production]`

**`scripts/backup-db.sh`**
- Creates compressed PostgreSQL database backups
- Includes automatic cleanup of old backups (30 days)
- Usage: `./backup-db.sh [staging|production]`

**`scripts/restore-db.sh`**
- Restores database from backup file
- Includes safety confirmations (especially for production)
- Usage: `./restore-db.sh <backup_file> [staging|production]`

### Environment Templates

**`.env.production.template`** & **`.env.staging.template`**
- Backend environment configuration templates
- Copy to `/home/tmsapp/tms-server/.env.production` or `.env.staging`
- Update with actual credentials and secrets

**`frontend-env.production.template`** & **`frontend-env.staging.template`**
- Frontend environment configuration templates
- Copy to `/home/tmsapp/tms-client/.env.production.local` or `.env.staging.local`
- Update with actual credentials and secrets

## Installation Instructions

### Initial Setup (One-time)

1. **Clone repositories on server:**
   ```bash
   cd /home/tmsapp
   git clone YOUR_BACKEND_REPO tms-server
   git clone YOUR_FRONTEND_REPO tms-client
   ```

2. **Copy and configure environment files:**
   ```bash
   # Backend
   cd /home/tmsapp/tms-server
   cp deployment/.env.staging.template .env.staging
   nano .env.staging  # Edit with actual values

   # Frontend
   cd /home/tmsapp/tms-client
   cp ../tms-server/deployment/frontend-env.staging.template .env.production.local
   nano .env.production.local  # Edit with actual values
   ```

3. **Install backend dependencies and run migrations:**
   ```bash
   cd /home/tmsapp/tms-server
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   ```

4. **Install frontend dependencies and build:**
   ```bash
   cd /home/tmsapp/tms-client
   npm install
   npm run build
   ```

5. **Install systemd services:**
   ```bash
   sudo cp /home/tmsapp/tms-server/deployment/systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable tms-backend tms-frontend
   sudo systemctl start tms-backend tms-frontend
   ```

6. **Install nginx configuration:**
   ```bash
   sudo cp /home/tmsapp/tms-server/deployment/nginx/tms-staging.conf /etc/nginx/sites-available/
   sudo ln -s /etc/nginx/sites-available/tms-staging.conf /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

7. **Setup SSL with Certbot:**
   ```bash
   sudo certbot --nginx -d tms-chat-staging.example.com
   ```

### Future Deployments

For updates after initial setup:

```bash
sudo su - tmsapp
cd /home/tmsapp/tms-server
./deployment/scripts/deploy.sh staging
```

## Common Tasks

### View Service Status

```bash
sudo systemctl status tms-backend
sudo systemctl status tms-frontend
sudo systemctl status nginx
```

### View Logs

```bash
# Backend logs (real-time)
sudo journalctl -u tms-backend -f

# Frontend logs (real-time)
sudo journalctl -u tms-frontend -f

# Nginx logs
sudo tail -f /var/log/nginx/tms-staging-access.log
sudo tail -f /var/log/nginx/tms-staging-error.log
```

### Restart Services

```bash
sudo systemctl restart tms-backend
sudo systemctl restart tms-frontend
sudo systemctl restart nginx
```

### Database Backup

```bash
# Manual backup
./deployment/scripts/backup-db.sh staging

# Setup automated daily backups (add to crontab)
crontab -e
# Add: 0 2 * * * /home/tmsapp/tms-server/deployment/scripts/backup-db.sh staging
```

### Database Restore

```bash
./deployment/scripts/restore-db.sh /path/to/backup.sql.gz staging
```

## Environment Variables Reference

### Critical Variables (Must Update)

Both backend and frontend require these to be updated:

1. **JWT_SECRET / NEXTAUTH_SECRET**
   - Must be identical across backend, frontend, and GCGC
   - Minimum 32 characters
   - Used for JWT token validation

2. **USER_MANAGEMENT_API_KEY**
   - API key for authenticating with GCGC
   - Obtain from GCGC admin

3. **OSS Credentials**
   - OSS_ACCESS_KEY_ID
   - OSS_ACCESS_KEY_SECRET
   - Required for file uploads

### Database Credentials

Already configured for Alibaba Cloud RDS:
- Production DB: `tms_production_db`
- Staging DB: `tms_staging_db`

### Redis Configuration

Already configured for Alibaba Cloud Redis:
- Production uses database 0
- Staging uses database 1

## Security Best Practices

1. **Never commit `.env` files to git**
   - Use `.env.example` or templates instead
   - Environment files contain sensitive credentials

2. **Use different secrets for staging and production**
   - Different API keys
   - Different JWT secrets (if using separate GCGC instances)

3. **Restrict file permissions**
   ```bash
   chmod 600 /home/tmsapp/tms-server/.env.production
   chmod 600 /home/tmsapp/tms-client/.env.production.local
   ```

4. **Use internal endpoints for database and Redis**
   - Already configured in templates
   - Reduces latency and bandwidth costs

5. **Enable firewall**
   ```bash
   sudo ufw enable
   sudo ufw allow 22/tcp  # SSH
   sudo ufw allow 80/tcp  # HTTP
   sudo ufw allow 443/tcp # HTTPS
   ```

## Troubleshooting

### Service won't start

1. Check logs: `sudo journalctl -u tms-backend -n 100`
2. Check environment file exists and is readable
3. Verify database connectivity
4. Check if port is already in use: `sudo lsof -i :8000`

### Nginx errors

1. Test configuration: `sudo nginx -t`
2. Check error logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify backend/frontend are running
4. Check DNS configuration: `nslookup tms-chat-staging.example.com`

### Database connection errors

1. Verify credentials in `.env` file
2. Test connection with psql:
   ```bash
   psql -h localhost \
        -U postgres -d tms_staging_db
   ```
3. Check firewall rules on RDS instance

### Authentication failures

1. Verify JWT_SECRET matches between backend, frontend, and GCGC
2. Check GCGC is accessible: `curl https://gcgc-team-management-system-staging.up.railway.app/health`
3. Verify USER_MANAGEMENT_API_KEY is correct

## Support

- Full deployment guide: `../DEPLOYMENT_GUIDE.md`
- Quick start guide: `QUICK_START.md`
- Backend documentation: `../CLAUDE.md`
- Issues: Contact your DevOps team

## License

Internal use only - GCGC Team Management System
