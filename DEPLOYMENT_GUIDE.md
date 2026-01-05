# TMS Deployment Guide - Alibaba Cloud

This guide covers deploying both TMS Server (FastAPI backend) and TMS Client (Next.js frontend) on a single Alibaba Cloud ECS instance.

## Architecture Overview

```
Internet (Port 80/443)
         ↓
    Nginx Reverse Proxy
    ├─→ Next.js Frontend (Port 3000)
    └─→ FastAPI Backend (Port 8000)
         ↓
    PostgreSQL RDS + Redis + OSS
```

## Infrastructure Details

### ECS Instances

**Production:**
- Instance ID: `i-5tshylo6ojndk2axjga3`
- Public IP: `47.80.71.165`
- Hostname: `tms-chat.example.com`
- OS: Ubuntu 22.04 LTS (recommended)

**Staging:**
- Instance ID: `i-5tshylo6ojndk2axjga2`
- Public IP: `47.80.66.95`
- Hostname: `tms-chat-staging.example.com`
- OS: Ubuntu 22.04 LTS (recommended)

### Database & Services

**PostgreSQL RDS:**
- Endpoint: `localhost:5432`
- Username: `postgres`
- Production DB: `tms_production_db`
- Staging DB: `tms_staging_db`

**Redis:**
- Endpoint: `localhost:6379`
- Password: `REDACTED_REDIS_PASSWORD`

**OSS:**
- Bucket: `tms-oss-goli`
- Region: `ap-southeast-6`
- Endpoint: `oss-ap-southeast-6.aliyuncs.com`

## Initial Server Setup

### 1. Connect to ECS Instance

```bash
# For Production
ssh root@47.80.71.165

# For Staging
ssh root@47.80.66.95
```

### 2. Install System Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nodejs \
    npm \
    nginx \
    git \
    curl \
    build-essential \
    postgresql-client

# Install Node.js 18.x (LTS)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installations
python3.11 --version
node --version
npm --version
nginx -v
```

### 3. Create Application User

```bash
# Create a non-root user for running applications
sudo useradd -m -s /bin/bash tmsapp
sudo usermod -aG sudo tmsapp

# Switch to tmsapp user
sudo su - tmsapp
```

## Application Deployment

### 4. Clone Repositories

```bash
cd /home/tmsapp

# Clone TMS Server (backend)
git clone https://github.com/YOUR_ORG/tms-server.git
cd tms-server
git checkout staging  # or main for production

# Clone TMS Client (frontend)
cd /home/tmsapp
git clone https://github.com/YOUR_ORG/tms-client.git
cd tms-client
git checkout staging  # or main for production
```

### 5. Setup Backend (FastAPI)

```bash
cd /home/tmsapp/tms-server

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment template and configure
cp .env.example .env.production  # or .env.staging
nano .env.production  # Edit with production credentials
```

**Backend Environment Variables** (`.env.production`):

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:REDACTED_DB_PASSWORD@localhost:5432/tms_production_db
DATABASE_URL_SYNC=postgresql://postgres:REDACTED_DB_PASSWORD@localhost:5432/tms_production_db

# Redis
REDIS_URL=redis://:REDACTED_REDIS_PASSWORD@localhost:6379/0

# User Management System (GCGC)
USER_MANAGEMENT_API_URL=https://gcgc-team-management-system-production.up.railway.app
USER_MANAGEMENT_API_KEY=your_gcgc_api_key_here
USER_MANAGEMENT_API_TIMEOUT=30
JWT_SECRET=your_gcgc_nextauth_secret_here  # MUST match GCGC's NEXTAUTH_SECRET

# Alibaba Cloud OSS
OSS_ACCESS_KEY_ID=your_oss_access_key_id
OSS_ACCESS_KEY_SECRET=your_oss_access_key_secret
OSS_BUCKET_NAME=tms-oss-goli
OSS_ENDPOINT=oss-ap-southeast-6.aliyuncs.com

# Application
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://tms-chat.example.com,https://www.tms-chat.example.com
```

```bash
# Run database migrations
source venv/bin/activate
alembic upgrade head

# Test the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+C to stop after testing
```

### 6. Setup Frontend (Next.js)

```bash
cd /home/tmsapp/tms-client

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.production.local
nano .env.production.local
```

**Frontend Environment Variables** (`.env.production.local`):

```env
# API URLs
NEXT_PUBLIC_API_URL=https://tms-chat.example.com/api
NEXT_PUBLIC_WS_URL=wss://tms-chat.example.com/ws

# GCGC Team Management System
NEXT_PUBLIC_USER_MANAGEMENT_URL=https://gcgc-team-management-system-production.up.railway.app

# NextAuth (must match backend JWT_SECRET)
NEXTAUTH_SECRET=your_gcgc_nextauth_secret_here
NEXTAUTH_URL=https://tms-chat.example.com

# Environment
NODE_ENV=production
```

```bash
# Build the frontend
npm run build

# Test the frontend
npm start
# Press Ctrl+C to stop after testing
```

## Service Configuration

### 7. Create Systemd Services

The systemd service files will automatically start your applications on boot and restart them if they crash.

**Backend Service** (`/etc/systemd/system/tms-backend.service`):

See `deployment/systemd/tms-backend.service` in this repository.

**Frontend Service** (`/etc/systemd/system/tms-frontend.service`):

See `deployment/systemd/tms-frontend.service` in this repository.

```bash
# Copy service files
sudo cp deployment/systemd/tms-backend.service /etc/systemd/system/
sudo cp deployment/systemd/tms-frontend.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable tms-backend tms-frontend

# Start services
sudo systemctl start tms-backend tms-frontend

# Check status
sudo systemctl status tms-backend
sudo systemctl status tms-frontend
```

### 8. Configure Nginx

**Production Nginx Config** (`/etc/nginx/sites-available/tms-production`):

See `deployment/nginx/tms-production.conf` in this repository.

**Staging Nginx Config** (`/etc/nginx/sites-available/tms-staging`):

See `deployment/nginx/tms-staging.conf` in this repository.

```bash
# Copy nginx configuration
sudo cp deployment/nginx/tms-production.conf /etc/nginx/sites-available/tms-production
# or for staging:
sudo cp deployment/nginx/tms-staging.conf /etc/nginx/sites-available/tms-staging

# Enable the site
sudo ln -s /etc/nginx/sites-available/tms-production /etc/nginx/sites-enabled/
# or for staging:
sudo ln -s /etc/nginx/sites-available/tms-staging /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### 9. Setup SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate for production
sudo certbot --nginx -d tms-chat.example.com -d www.tms-chat.example.com

# Or for staging
sudo certbot --nginx -d tms-chat-staging.example.com

# Certbot will automatically configure HTTPS and set up auto-renewal

# Test auto-renewal
sudo certbot renew --dry-run
```

## Deployment Scripts

### 10. Use Deployment Scripts for Updates

```bash
# Make deployment script executable
chmod +x deployment/scripts/deploy.sh

# Deploy to staging
./deployment/scripts/deploy.sh staging

# Deploy to production
./deployment/scripts/deploy.sh production
```

## Monitoring & Maintenance

### View Logs

```bash
# Backend logs
sudo journalctl -u tms-backend -f

# Frontend logs
sudo journalctl -u tms-frontend -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
# Restart backend only
sudo systemctl restart tms-backend

# Restart frontend only
sudo systemctl restart tms-frontend

# Restart nginx
sudo systemctl restart nginx

# Restart all
sudo systemctl restart tms-backend tms-frontend nginx
```

### Update Application

```bash
# Use deployment script (recommended)
./deployment/scripts/deploy.sh production

# Or manually:
cd /home/tmsapp/tms-server
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart tms-backend

cd /home/tmsapp/tms-client
git pull origin main
npm install
npm run build
sudo systemctl restart tms-frontend
```

## Security Checklist

- [ ] Configure UFW firewall (allow 80, 443, SSH)
- [ ] Change default SSH port
- [ ] Disable root login via SSH
- [ ] Setup SSH key-based authentication
- [ ] Configure fail2ban
- [ ] Enable automatic security updates
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Setup monitoring (e.g., Prometheus + Grafana)

### Firewall Setup

```bash
# Enable firewall
sudo ufw enable

# Allow SSH (change 22 to your custom port if changed)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

## Troubleshooting

### Backend not starting

```bash
# Check logs
sudo journalctl -u tms-backend -n 100

# Check if database is reachable
psql -h localhost -U postgres -d tms_production_db

# Check if port 8000 is in use
sudo lsof -i :8000
```

### Frontend not starting

```bash
# Check logs
sudo journalctl -u tms-frontend -n 100

# Check if port 3000 is in use
sudo lsof -i :3000

# Rebuild frontend
cd /home/tmsapp/tms-client
npm run build
```

### Nginx errors

```bash
# Check nginx configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Verify DNS is pointing to correct IP
nslookup tms-chat.example.com
```

### SSL certificate issues

```bash
# Renew certificate manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates
```

## Backup Strategy

### Database Backups

```bash
# Create backup script at /home/tmsapp/backup-db.sh
chmod +x /home/tmsapp/backup-db.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/tmsapp/backup-db.sh
```

See `deployment/scripts/backup-db.sh` for the backup script.

## Performance Optimization

### Nginx Caching

Already configured in nginx config files for static assets.

### Database Connection Pooling

FastAPI SQLAlchemy settings in `app/config.py`:
- Pool size: 20
- Max overflow: 10
- Pool recycle: 3600 seconds

### Redis Configuration

- Maxmemory policy: allkeys-lru
- Maxmemory: 256mb (adjust based on instance size)

## Cost Optimization

1. **Use internal endpoints** for RDS and Redis (already configured in Private endpoints)
2. **Enable OSS lifecycle policies** to move old files to cheaper storage
3. **Configure log rotation** to prevent disk space issues
4. **Monitor resource usage** and right-size your ECS instance

## Next Steps

1. Set up domain DNS records to point to your ECS public IPs
2. Configure monitoring and alerting
3. Set up automated backups
4. Create CI/CD pipeline (GitHub Actions or Alibaba Cloud DevOps)
5. Load testing before going live

## Support

For issues or questions:
- Backend: See `CLAUDE.md` in tms-server repository
- Frontend: See `CLAUDE.md` in tms-client repository
- Infrastructure: Contact your DevOps team
