# TMS Deployment Checklist

Use this checklist to track your deployment progress.

## Pre-Deployment (Before touching servers)

### 1. Credentials Ready ✓/✗
- [ ] ECS SSH access (test: `ssh root@47.80.66.95`)
- [ ] Database password: `REDACTED_DB_PASSWORD`
- [ ] Redis password: `REDACTED_REDIS_PASSWORD`
- [ ] OSS Access Key ID (from senior/infra team)
- [ ] OSS Access Key Secret (from senior/infra team)
- [ ] JWT secrets from Railway (already have ✓)
- [ ] GCGC API key (already have ✓)

### 2. DNS Configuration ✓/✗
- [ ] A record: `tms-chat-staging.example.com` → `47.80.66.95`
- [ ] A record: `tms-chat.example.com` → `47.80.71.165`
- [ ] TTL set low (300s) for easy updates
- [ ] Wait 5-60 minutes for propagation
- [ ] Test: `nslookup tms-chat-staging.example.com`

## Initial Server Setup (Do once per server)

### 3. Connect to Staging Server ✓/✗
```bash
ssh root@47.80.66.95
```

### 4. Install System Dependencies ✓/✗
```bash
# Update system
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

# Install Node.js 18.x LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installations
python3.11 --version
node --version
nginx -v
```

### 5. Create Application User ✓/✗
```bash
# Create user
sudo useradd -m -s /bin/bash tmsapp
sudo usermod -aG sudo tmsapp

# Switch to tmsapp user
sudo su - tmsapp
cd ~
```

### 6. Clone Repositories ✓/✗
```bash
# Clone backend
git clone <YOUR_TMS_SERVER_REPO_URL> tms-server
cd tms-server
git checkout staging  # or main for production

# Clone frontend
cd /home/tmsapp
git clone <YOUR_TMS_CLIENT_REPO_URL> tms-client
cd tms-client
git checkout staging  # or main for production
```

## Backend Setup

### 7. Setup Python Environment ✓/✗
```bash
cd /home/tmsapp/tms-server

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 8. Configure Backend Environment ✓/✗
```bash
cd /home/tmsapp/tms-server

# Copy environment file
cp .env.staging.example .env.staging

# Edit with actual credentials
nano .env.staging

# CRITICAL: Update these values:
# 1. OSS_ACCESS_KEY_ID=<from infra key>
# 2. OSS_ACCESS_KEY_SECRET=<from infra key>
# 3. Verify all other values match the examples

# Test environment file
source venv/bin/activate
python -c "from app.config import settings; print('Database:', settings.DATABASE_URL[:50])"
```

### 9. Run Database Migrations ✓/✗
```bash
cd /home/tmsapp/tms-server
source venv/bin/activate

# Run migrations
alembic upgrade head

# Verify tables created
psql -h localhost \
     -U postgres -d tms_staging_db -c '\dt'
```

### 10. Test Backend Manually ✓/✗
```bash
cd /home/tmsapp/tms-server
source venv/bin/activate

# Start backend (foreground test)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, test:
curl http://localhost:8000/health
# Should return: {"status": "healthy"}

# Press Ctrl+C to stop
```

## Frontend Setup

### 11. Install Frontend Dependencies ✓/✗
```bash
cd /home/tmsapp/tms-client

# Install packages
npm ci
```

### 12. Configure Frontend Environment ✓/✗
```bash
cd /home/tmsapp/tms-client

# Copy environment file
cp ../tms-server/deployment/frontend.env.staging.alibaba .env.production.local

# Edit if needed
nano .env.production.local

# Verify values:
# - NEXTAUTH_SECRET matches backend
# - NEXT_PUBLIC_API_URL points to correct domain
# - All GCGC URLs are correct
```

### 13. Build Frontend ✓/✗
```bash
cd /home/tmsapp/tms-client

# Build Next.js
npm run build

# Should complete without errors
```

### 14. Test Frontend Manually ✓/✗
```bash
cd /home/tmsapp/tms-client

# Start frontend (foreground test)
npm start

# In another terminal, test:
curl http://localhost:3000
# Should return HTML

# Press Ctrl+C to stop
```

## Service Installation

### 15. Install Systemd Services ✓/✗
```bash
# Exit to root user
exit

# Copy service files
sudo cp /home/tmsapp/tms-server/deployment/systemd/tms-backend.service /etc/systemd/system/
sudo cp /home/tmsapp/tms-server/deployment/systemd/tms-frontend.service /etc/systemd/system/

# Edit to set correct environment file
sudo nano /etc/systemd/system/tms-backend.service
# Change: EnvironmentFile=/home/tmsapp/tms-server/.env.staging

sudo nano /etc/systemd/system/tms-frontend.service
# Change: EnvironmentFile=/home/tmsapp/tms-client/.env.production.local

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable tms-backend
sudo systemctl enable tms-frontend

# Start services
sudo systemctl start tms-backend
sudo systemctl start tms-frontend

# Check status
sudo systemctl status tms-backend
sudo systemctl status tms-frontend
# Both should show: active (running)
```

## Nginx Configuration

### 16. Install Nginx Configuration ✓/✗
```bash
# Copy nginx config
sudo cp /home/tmsapp/tms-server/deployment/nginx/tms-staging.conf /etc/nginx/sites-available/tms-staging

# Enable site
sudo ln -s /etc/nginx/sites-available/tms-staging /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t
# Should show: syntax is ok

# Restart nginx
sudo systemctl restart nginx
```

### 17. Test Without SSL (HTTP) ✓/✗
```bash
# Test locally on server
curl http://localhost
# Should return HTML from frontend

curl http://localhost/api/v1/health
# Should return API health

# Test from your computer
curl http://47.80.66.95
# Should work if firewall allows
```

## SSL Certificate Setup

### 18. Configure Firewall ✓/✗
```bash
# Enable firewall
sudo ufw enable

# Allow SSH (IMPORTANT - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
# Should show: Status: active
```

### 19. Install SSL Certificate ✓/✗
```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d tms-chat-staging.example.com

# Follow prompts:
# - Enter email
# - Agree to terms
# - Choose redirect HTTP to HTTPS: Yes

# Test auto-renewal
sudo certbot renew --dry-run
```

## Verification

### 20. Test HTTPS Endpoints ✓/✗
```bash
# From your computer:

# Test frontend
curl -I https://tms-chat-staging.example.com
# Should return: HTTP/2 200

# Test backend health
curl https://tms-chat-staging.example.com/health

# Test API health
curl https://tms-chat-staging.example.com/api/v1/health

# Test API docs (staging only)
# Open in browser:
https://tms-chat-staging.example.com/docs
```

### 21. Test Application Features ✓/✗
Open in browser: `https://tms-chat-staging.example.com`

- [ ] Page loads without errors
- [ ] Redirects to GCGC login
- [ ] Can login with GCGC credentials
- [ ] Redirects back to TMS after login
- [ ] Can see conversations
- [ ] Can send a message
- [ ] Messages appear in real-time
- [ ] Can upload files (if OSS configured)
- [ ] WebSocket connected (check browser console)

### 22. Monitor Logs ✓/✗
```bash
# Backend logs
sudo journalctl -u tms-backend -f

# Frontend logs
sudo journalctl -u tms-frontend -f

# Nginx logs
sudo tail -f /var/log/nginx/tms-staging-access.log
sudo tail -f /var/log/nginx/tms-staging-error.log
```

## Post-Deployment

### 23. Setup Database Backups ✓/✗
```bash
# As tmsapp user
sudo su - tmsapp

# Create backups directory
mkdir -p /home/tmsapp/backups/database

# Test backup script
cd /home/tmsapp/tms-server
./deployment/scripts/backup-db.sh staging

# Setup cron job
crontab -e
# Add this line:
0 2 * * * /home/tmsapp/tms-server/deployment/scripts/backup-db.sh staging
```

### 24. Document Deployment ✓/✗
- [ ] Save all credentials securely
- [ ] Document any custom configurations
- [ ] Update team wiki/docs
- [ ] Share access with team members

## Production Deployment

After staging is verified and working:

### 25. Repeat for Production ✓/✗
```bash
# SSH to production server
ssh root@47.80.71.165

# Follow steps 4-19 again but:
# - Use .env.production instead of .env.staging
# - Use frontend.env.production.alibaba
# - Use tms-production nginx config
# - Use tms-chat.example.com for SSL
# - Checkout main/master branch instead of staging
```

## Quick Verification Script

Save this as `verify.sh` and run on server:

```bash
#!/bin/bash
echo "=== TMS Deployment Status ==="
echo ""
echo "Services:"
systemctl is-active nginx && echo "✓ Nginx running" || echo "✗ Nginx stopped"
systemctl is-active tms-backend && echo "✓ Backend running" || echo "✗ Backend stopped"
systemctl is-active tms-frontend && echo "✓ Frontend running" || echo "✗ Frontend stopped"
echo ""
echo "Ports:"
netstat -tlnp | grep :80 > /dev/null && echo "✓ HTTP listening" || echo "✗ HTTP not listening"
netstat -tlnp | grep :443 > /dev/null && echo "✓ HTTPS listening" || echo "✗ HTTPS not listening"
netstat -tlnp | grep :8000 > /dev/null && echo "✓ Backend listening" || echo "✗ Backend not listening"
netstat -tlnp | grep :3000 > /dev/null && echo "✓ Frontend listening" || echo "✗ Frontend not listening"
echo ""
echo "SSL Certificate:"
certbot certificates 2>/dev/null | grep -A3 "tms-chat" || echo "No certificate found"
```

## Troubleshooting Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| 502 Bad Gateway | `sudo systemctl restart tms-backend tms-frontend` |
| DNS not resolving | Wait 30-60 min for propagation |
| SSL errors | `sudo certbot renew --force-renewal && sudo systemctl restart nginx` |
| Can't login | Check JWT_SECRET matches across all apps |
| WebSocket fails | Check Nginx WebSocket config |
| File upload fails | Verify OSS credentials in .env |

## Support

- **Quick Start**: `deployment/QUICK_START.md`
- **Full Guide**: `DEPLOYMENT_GUIDE.md`
- **Verification**: `deployment/VERIFY_DEPLOYMENT.md`
- **OSS Setup**: `deployment/GET_OSS_CREDENTIALS.md`

---

**Current Status**: ⬜ Not Started | 🟡 In Progress | ✅ Complete

Mark each checkbox as you complete steps!
