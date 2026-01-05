#!/bin/bash
# TMS Deployment Helper Script
# This script helps you deploy TMS to Alibaba Cloud step-by-step

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TMS Deployment Helper${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Set up SSH key
echo -e "${YELLOW}Step 1: Setting up SSH key${NC}"
echo ""

if [ -f ~/Downloads/sogo-infra-key.pem ]; then
    echo "Found sogo-infra-key.pem in Downloads"

    # Move to .ssh
    mkdir -p ~/.ssh
    mv ~/Downloads/sogo-infra-key.pem ~/.ssh/
    echo "✓ Moved to ~/.ssh/"

    # Set permissions
    chmod 600 ~/.ssh/sogo-infra-key.pem
    echo "✓ Set secure permissions (600)"

elif [ -f ~/.ssh/sogo-infra-key.pem ]; then
    echo "Key already in ~/.ssh/"
    chmod 600 ~/.ssh/sogo-infra-key.pem
    echo "✓ Ensured secure permissions"
else
    echo -e "${RED}Error: sogo-infra-key.pem not found!${NC}"
    echo "Please ensure the key is in ~/Downloads/"
    exit 1
fi

# Step 2: Create SSH config
echo ""
echo -e "${YELLOW}Step 2: Creating SSH config${NC}"
echo ""

cat >> ~/.ssh/config << 'EOF'

# TMS Servers - Alibaba Cloud
Host tms-staging
    HostName 47.80.66.95
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host tms-production
    HostName 47.80.71.165
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF

echo "✓ SSH config created"

# Step 3: Test connection
echo ""
echo -e "${YELLOW}Step 3: Testing SSH connection to staging${NC}"
echo ""

if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 tms-staging "echo 'SSH connection successful!'" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH connection to staging works!${NC}"
else
    echo -e "${RED}✗ Cannot connect to staging server${NC}"
    echo "Please check:"
    echo "  1. Key file is correct"
    echo "  2. Server is running"
    echo "  3. Firewall allows SSH (port 22)"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SSH Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "You can now connect with:"
echo -e "  ${YELLOW}ssh tms-staging${NC}"
echo -e "  ${YELLOW}ssh tms-production${NC}"
echo ""
echo -e "${YELLOW}Next: Run the deployment commands manually or use:${NC}"
echo -e "  ${YELLOW}./deployment/deploy-to-staging.sh${NC}"
