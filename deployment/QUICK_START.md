# TMS Deployment Quick Start Guide

This guide will help you quickly deploy TMS Server and Client on Alibaba Cloud ECS.

## Prerequisites

- Access to ECS instance (SSH)
- Git repositories access
- GCGC API credentials
- Alibaba Cloud OSS credentials
- Domain DNS configured to point to ECS public IP

## Deployment Checklist

### 1. Initial Server Setup (One-time)

Connect to your ECS instance:

```bash
# For Staging
ssh root@47.80.66.95

# For Production
ssh root@47.80.71.165
```

Run the initial setup:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm nginx git curl build-essential postgresql-client

# Install Node.js 18.x LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Create application user
sudo useradd -m -s /bin/bash tmsapp
sudo usermod -aG sudo tmsapp

# Switch to tmsapp user
sudo su - tmsapp
```

### 2. Clone Repositories

```bash
cd /home/tmsapp

# Clone backend
git clone YOUR_BACKEND_REPO_URL tms-server
cd tms-server
git checkout staging  # or main for production

# Clone frontend
cd /home/tmsapp
git clone YOUR_FRONTEND_REPO_URL tms-client
cd tms-client
git checkout staging  # or main for production
```

### 3. Setup Backend

```bash
cd /home/tmsapp/tms-server

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy and configure environment
cp deployment/.env.staging.template .env.staging
# OR for production:
# cp deployment/.env.production.template .env.production

# Edit environment file with your credentials
nano .env.staging

# IMPORTANT: Update these values:
# - JWT_SECRET (must match GCGC's NEXTAUTH_SECRET)
# - USER_MANAGEMENT_API_KEY
# - OSS_ACCESS_KEY_ID
# - OSS_ACCESS_KEY_SECRET

# Run migrations
alembic upgrade head

# Test backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+C after verifying it works
```

### 4. Setup Frontend

```bash
cd /home/tmsapp/tms-client

# Install dependencies
npm install

# Copy and configure environment
cp ../tms-server/deployment/frontend-env.staging.template .env.production.local
# OR for production:
# cp ../tms-server/deployment/frontend-env.production.template .env.production.local

# Edit environment file
nano .env.production.local

# IMPORTANT: Update these values:
# - NEXTAUTH_SECRET (must match backend and GCGC)
# - NEXT_PUBLIC_USER_MANAGEMENT_URL

# Build frontend
npm run build

# Test frontend
npm start
# Press Ctrl+C after verifying it works
```

### 5. Install Services

```bash
# Exit tmsapp user to run as root
exit

# Copy systemd service files
sudo cp /home/tmsapp/tms-server/deployment/systemd/tms-backend.service /etc/systemd/system/
sudo cp /home/tmsapp/tms-server/deployment/systemd/tms-frontend.service /etc/systemd/system/

# Edit service files to set correct environment file
sudo nano /etc/systemd/system/tms-backend.service
# Change EnvironmentFile to .env.staging or .env.production

sudo nano /etc/systemd/system/tms-frontend.service
# Change EnvironmentFile to .env.staging.local or .env.production.local

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable tms-backend tms-frontend
sudo systemctl start tms-backend tms-frontend

# Check status
sudo systemctl status tms-backend
sudo systemctl status tms-frontend
```

### 6. Configure Nginx

```bash
# Copy nginx configuration
sudo cp /home/tmsapp/tms-server/deployment/nginx/tms-staging.conf /etc/nginx/sites-available/tms-staging
# OR for production:
# sudo cp /home/tmsapp/tms-server/deployment/nginx/tms-production.conf /etc/nginx/sites-available/tms-production

# Enable the site
sudo ln -s /etc/nginx/sites-available/tms-staging /etc/nginx/sites-enabled/
# OR for production:
# sudo ln -s /etc/nginx/sites-available/tms-production /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### 7. Setup SSL Certificate

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
# For staging:
sudo certbot --nginx -d tms-chat-staging.example.com

# For production:
sudo certbot --nginx -d tms-chat.example.com -d www.tms-chat.example.com

# Test auto-renewal
sudo certbot renew --dry-run
```

### 8. Configure Firewall

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

### 9. Setup Database Backups

```bash
# Switch back to tmsapp user
sudo su - tmsapp

# Create backups directory
mkdir -p /home/tmsapp/backups/database

# Make backup script executable (already done if cloned from git)
chmod +x /home/tmsapp/tms-server/deployment/scripts/backup-db.sh

# Test backup
/home/tmsapp/tms-server/deployment/scripts/backup-db.sh staging

# Setup cron job for daily backups
crontab -e
# Add this line:
# 0 2 * * * /home/tmsapp/tms-server/deployment/scripts/backup-db.sh staging
```

### 10. Verify Deployment

```bash
# Check all services are running
sudo systemctl status tms-backend tms-frontend nginx

# Check backend logs
sudo journalctl -u tms-backend -n 50

# Check frontend logs
sudo journalctl -u tms-frontend -n 50

# Test endpoints
curl https://tms-chat-staging.example.com/health
curl https://tms-chat-staging.example.com/api/v1/health
```

## Future Deployments

After initial setup, use the deployment script:

```bash
sudo su - tmsapp
cd /home/tmsapp/tms-server
./deployment/scripts/deploy.sh staging
# OR for production:
# ./deployment/scripts/deploy.sh production
```

## Useful Commands

### View Logs

```bash
# Backend logs (real-time)
sudo journalctl -u tms-backend -f

# Frontend logs (real-time)
sudo journalctl -u tms-frontend -f

# Nginx access logs
sudo tail -f /var/log/nginx/tms-staging-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/tms-staging-error.log
```

### Restart Services

```bash
# Restart backend
sudo systemctl restart tms-backend

# Restart frontend
sudo systemctl restart tms-frontend

# Restart nginx
sudo systemctl restart nginx

# Restart all
sudo systemctl restart tms-backend tms-frontend nginx
```

### Database Operations

```bash
# Run migrations
cd /home/tmsapp/tms-server
source venv/bin/activate
alembic upgrade head

# Create manual backup
/home/tmsapp/tms-server/deployment/scripts/backup-db.sh staging

# Restore from backup
/home/tmsapp/tms-server/deployment/scripts/restore-db.sh /path/to/backup.sql.gz staging
```

## Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u tms-backend -n 100 --no-pager

# Check if port 8000 is in use
sudo lsof -i :8000

# Test database connection
cd /home/tmsapp/tms-server
source venv/bin/activate
python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

### Frontend won't start

```bash
# Check logs
sudo journalctl -u tms-frontend -n 100 --no-pager

# Check if port 3000 is in use
sudo lsof -i :3000

# Rebuild frontend
cd /home/tmsapp/tms-client
npm run build
```

### SSL certificate issues

```bash
# Check certificate status
sudo certbot certificates

# Renew manually
sudo certbot renew --force-renewal
```

### Can't access website

```bash
# Check DNS
nslookup tms-chat-staging.example.com

# Check nginx
sudo nginx -t
sudo systemctl status nginx

# Check firewall
sudo ufw status

# Check if services are listening
sudo netstat -tlnp | grep -E ':(80|443|3000|8000)'
```

## Security Hardening (Recommended)

```bash
# Change SSH port (edit /etc/ssh/sshd_config)
sudo nano /etc/ssh/sshd_config
# Change Port 22 to Port 2222
sudo systemctl restart sshd

# Disable root login
sudo nano /etc/ssh/sshd_config
# Set PermitRootLogin no
sudo systemctl restart sshd

# Install fail2ban
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Enable automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

## Next Steps

1. Test all application features thoroughly
2. Set up monitoring (Prometheus, Grafana, or cloud monitoring)
3. Configure log rotation to prevent disk space issues
4. Set up automated backups to Alibaba Cloud OSS
5. Create CI/CD pipeline for automated deployments
6. Document any custom configurations or changes

## Support

- Deployment Guide: `DEPLOYMENT_GUIDE.md`
- Backend Documentation: `CLAUDE.md`
- Issues: Contact your DevOps team
