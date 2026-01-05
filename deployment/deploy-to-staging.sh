#!/bin/bash
# Complete TMS Staging Deployment Script
# This deploys both backend and frontend to Alibaba Cloud staging server

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TMS Staging Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check SSH connection
echo -e "${YELLOW}Checking SSH connection...${NC}"
if ! ssh -o ConnectTimeout=10 tms-staging "echo 'Connected'" 2>/dev/null; then
    echo -e "${RED}Cannot connect to staging server!${NC}"
    echo "Please run: ssh tms-staging"
    exit 1
fi
echo -e "${GREEN}✓ SSH connection OK${NC}"
echo ""

# Step 1: Update system and install dependencies
echo -e "${YELLOW}Step 1: Installing system dependencies...${NC}"
ssh tms-staging << 'ENDSSH'
set -e
export DEBIAN_FRONTEND=noninteractive

echo "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

echo "Installing required packages..."
apt-get install -y -qq \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    git \
    curl \
    build-essential \
    postgresql-client \
    redis-tools

echo "Installing Node.js 18.x..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y -qq nodejs

echo "Verifying installations..."
python3.11 --version
node --version
npm --version
nginx -v

echo "✓ System dependencies installed"
ENDSSH

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 2: Create application user
echo -e "${YELLOW}Step 2: Creating application user...${NC}"
ssh tms-staging << 'ENDSSH'
if ! id -u tmsapp > /dev/null 2>&1; then
    useradd -m -s /bin/bash tmsapp
    usermod -aG sudo tmsapp
    echo "✓ User 'tmsapp' created"
else
    echo "✓ User 'tmsapp' already exists"
fi
ENDSSH

echo -e "${GREEN}✓ Application user ready${NC}"
echo ""

# Step 3: Clone repositories
echo -e "${YELLOW}Step 3: Cloning repositories...${NC}"
echo ""
echo -e "${YELLOW}What is your TMS Server repository URL?${NC}"
read -p "Backend repo URL: " BACKEND_REPO
echo ""
echo -e "${YELLOW}What is your TMS Client repository URL?${NC}"
read -p "Frontend repo URL: " FRONTEND_REPO

ssh tms-staging << ENDSSH
set -e
sudo -u tmsapp bash << 'EOF'
cd /home/tmsapp

# Clone backend
if [ ! -d "tms-server" ]; then
    echo "Cloning backend..."
    git clone ${BACKEND_REPO} tms-server
    cd tms-server
    git checkout staging
    echo "✓ Backend cloned"
else
    echo "✓ Backend already cloned"
    cd tms-server
    git pull origin staging
fi

cd /home/tmsapp

# Clone frontend
if [ ! -d "tms-client" ]; then
    echo "Cloning frontend..."
    git clone ${FRONTEND_REPO} tms-client
    cd tms-client
    git checkout staging
    echo "✓ Frontend cloned"
else
    echo "✓ Frontend already cloned"
    cd tms-client
    git pull origin staging
fi
EOF
ENDSSH

echo -e "${GREEN}✓ Repositories cloned${NC}"
echo ""

# Step 4: Setup backend
echo -e "${YELLOW}Step 4: Setting up backend...${NC}"

# Get OSS credentials
echo ""
echo -e "${YELLOW}Please enter your Alibaba Cloud OSS credentials:${NC}"
read -p "OSS Access Key ID: " OSS_KEY_ID
read -sp "OSS Access Key Secret: " OSS_KEY_SECRET
echo ""

# Create backend .env file
ssh tms-staging "sudo -u tmsapp bash" << EOF
cd /home/tmsapp/tms-server

# Copy environment template
cp .env.staging.example .env.staging

# Update OSS credentials
sed -i 's/YOUR_OSS_ACCESS_KEY_ID_HERE/${OSS_KEY_ID}/' .env.staging
sed -i 's/YOUR_OSS_ACCESS_KEY_SECRET_HERE/${OSS_KEY_SECRET}/' .env.staging

echo "✓ Environment file configured"

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "✓ Python dependencies installed"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "✓ Migrations complete"
EOF

echo -e "${GREEN}✓ Backend configured${NC}"
echo ""

# Step 5: Setup frontend
echo -e "${YELLOW}Step 5: Setting up frontend...${NC}"

ssh tms-staging "sudo -u tmsapp bash" << 'EOF'
cd /home/tmsapp/tms-client

# Copy environment template
cp ../tms-server/deployment/frontend.env.staging.alibaba .env.production.local

echo "✓ Environment file configured"

# Install dependencies
echo "Installing Node.js dependencies..."
npm ci -q

echo "✓ Dependencies installed"

# Build frontend
echo "Building Next.js application..."
npm run build

echo "✓ Build complete"
EOF

echo -e "${GREEN}✓ Frontend configured${NC}"
echo ""

# Step 6: Install systemd services
echo -e "${YELLOW}Step 6: Installing systemd services...${NC}"

ssh tms-staging << 'ENDSSH'
# Copy service files
cp /home/tmsapp/tms-server/deployment/systemd/tms-backend.service /etc/systemd/system/
cp /home/tmsapp/tms-server/deployment/systemd/tms-frontend.service /etc/systemd/system/

# Update environment file paths
sed -i 's|EnvironmentFile=.*|EnvironmentFile=/home/tmsapp/tms-server/.env.staging|' /etc/systemd/system/tms-backend.service
sed -i 's|EnvironmentFile=.*|EnvironmentFile=/home/tmsapp/tms-client/.env.production.local|' /etc/systemd/system/tms-frontend.service

# Reload systemd
systemctl daemon-reload

# Enable and start services
systemctl enable tms-backend tms-frontend
systemctl start tms-backend
sleep 3
systemctl start tms-frontend
sleep 3

# Check status
if systemctl is-active --quiet tms-backend; then
    echo "✓ Backend service running"
else
    echo "✗ Backend service failed"
    journalctl -u tms-backend -n 20
fi

if systemctl is-active --quiet tms-frontend; then
    echo "✓ Frontend service running"
else
    echo "✗ Frontend service failed"
    journalctl -u tms-frontend -n 20
fi
ENDSSH

echo -e "${GREEN}✓ Services installed${NC}"
echo ""

# Step 7: Configure Nginx
echo -e "${YELLOW}Step 7: Configuring Nginx...${NC}"

ssh tms-staging << 'ENDSSH'
# Copy nginx config
cp /home/tmsapp/tms-server/deployment/nginx/tms-staging.conf /etc/nginx/sites-available/tms-staging

# Enable site
ln -sf /etc/nginx/sites-available/tms-staging /etc/nginx/sites-enabled/

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

# Restart nginx
systemctl restart nginx

echo "✓ Nginx configured"
ENDSSH

echo -e "${GREEN}✓ Nginx configured${NC}"
echo ""

# Step 8: Configure firewall
echo -e "${YELLOW}Step 8: Configuring firewall...${NC}"

ssh tms-staging << 'ENDSSH'
# Enable firewall
yes | ufw enable

# Allow ports
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

ufw status

echo "✓ Firewall configured"
ENDSSH

echo -e "${GREEN}✓ Firewall configured${NC}"
echo ""

# Step 9: Install SSL certificate
echo -e "${YELLOW}Step 9: Installing SSL certificate...${NC}"

ssh tms-staging << 'ENDSSH'
# Install certbot
apt-get install -y -qq certbot python3-certbot-nginx

# Obtain certificate
certbot --nginx -d tms-chat-staging.example.com --non-interactive --agree-tos --email admin@example.com --redirect

echo "✓ SSL certificate installed"
ENDSSH

echo -e "${GREEN}✓ SSL certificate installed${NC}"
echo ""

# Step 10: Verify deployment
echo -e "${YELLOW}Step 10: Verifying deployment...${NC}"
echo ""

sleep 5

echo "Testing endpoints..."
curl -I https://tms-chat-staging.example.com 2>&1 | head -1
curl https://tms-chat-staging.example.com/health 2>&1
curl https://tms-chat-staging.example.com/api/v1/health 2>&1

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your TMS Chat is now accessible at:"
echo -e "  ${GREEN}https://tms-chat-staging.example.com${NC}"
echo ""
echo "API Documentation:"
echo -e "  ${GREEN}https://tms-chat-staging.example.com/docs${NC}"
echo ""
echo "View logs:"
echo -e "  ${YELLOW}ssh tms-staging 'journalctl -u tms-backend -f'${NC}"
echo -e "  ${YELLOW}ssh tms-staging 'journalctl -u tms-frontend -f'${NC}"
