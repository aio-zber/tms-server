#!/bin/bash
# TMS Deployment Script
# Usage: ./deploy.sh [staging|production]

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
APP_USER="tmsapp"
APP_DIR="/home/$APP_USER"
BACKEND_DIR="$APP_DIR/tms-server"
FRONTEND_DIR="$APP_DIR/tms-client"

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}Error: Invalid environment. Use 'staging' or 'production'${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TMS Deployment Script${NC}"
echo -e "${GREEN}Environment: $ENVIRONMENT${NC}"
echo -e "${GREEN}========================================${NC}"

# Function to print step
print_step() {
    echo -e "\n${YELLOW}>>> $1${NC}"
}

# Function to check if running as correct user
check_user() {
    if [[ $(whoami) != "$APP_USER" ]]; then
        echo -e "${RED}Error: This script must be run as $APP_USER user${NC}"
        echo -e "${YELLOW}Run: sudo su - $APP_USER${NC}"
        exit 1
    fi
}

# Function to deploy backend
deploy_backend() {
    print_step "Deploying Backend (FastAPI)"

    cd "$BACKEND_DIR"

    # Determine branch
    if [[ "$ENVIRONMENT" == "production" ]]; then
        BRANCH="main"
    else
        BRANCH="staging"
    fi

    # Pull latest code
    print_step "Pulling latest code from $BRANCH branch"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"

    # Activate virtual environment
    source venv/bin/activate

    # Install/update dependencies
    print_step "Installing Python dependencies"
    pip install --upgrade pip
    pip install -r requirements.txt

    # Run database migrations
    print_step "Running database migrations"
    alembic upgrade head

    # Restart backend service
    print_step "Restarting backend service"
    sudo systemctl restart tms-backend

    # Wait for service to start
    sleep 3

    # Check service status
    if sudo systemctl is-active --quiet tms-backend; then
        echo -e "${GREEN}✓ Backend service is running${NC}"
    else
        echo -e "${RED}✗ Backend service failed to start${NC}"
        sudo systemctl status tms-backend
        exit 1
    fi

    deactivate
}

# Function to deploy frontend
deploy_frontend() {
    print_step "Deploying Frontend (Next.js)"

    cd "$FRONTEND_DIR"

    # Determine branch
    if [[ "$ENVIRONMENT" == "production" ]]; then
        BRANCH="main"
    else
        BRANCH="staging"
    fi

    # Pull latest code
    print_step "Pulling latest code from $BRANCH branch"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"

    # Install dependencies
    print_step "Installing Node.js dependencies"
    npm ci --production=false

    # Build frontend
    print_step "Building Next.js application"
    npm run build

    # Restart frontend service
    print_step "Restarting frontend service"
    sudo systemctl restart tms-frontend

    # Wait for service to start
    sleep 3

    # Check service status
    if sudo systemctl is-active --quiet tms-frontend; then
        echo -e "${GREEN}✓ Frontend service is running${NC}"
    else
        echo -e "${RED}✗ Frontend service failed to start${NC}"
        sudo systemctl status tms-frontend
        exit 1
    fi
}

# Function to reload nginx
reload_nginx() {
    print_step "Reloading Nginx"
    sudo nginx -t && sudo systemctl reload nginx
    echo -e "${GREEN}✓ Nginx reloaded${NC}"
}

# Function to show deployment summary
show_summary() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Summary${NC}"
    echo -e "${GREEN}========================================${NC}"

    # Backend status
    echo -e "\nBackend Status:"
    sudo systemctl status tms-backend --no-pager -l | head -n 10

    # Frontend status
    echo -e "\nFrontend Status:"
    sudo systemctl status tms-frontend --no-pager -l | head -n 10

    # Nginx status
    echo -e "\nNginx Status:"
    sudo systemctl status nginx --no-pager -l | head -n 5

    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"

    # Show URLs
    if [[ "$ENVIRONMENT" == "production" ]]; then
        echo -e "\nProduction URLs:"
        echo -e "  Frontend: ${GREEN}https://tms-chat.example.com${NC}"
        echo -e "  API: ${GREEN}https://tms-chat.example.com/api${NC}"
        echo -e "  API Docs: ${GREEN}https://tms-chat.example.com/docs${NC}"
    else
        echo -e "\nStaging URLs:"
        echo -e "  Frontend: ${GREEN}https://tms-chat-staging.example.com${NC}"
        echo -e "  API: ${GREEN}https://tms-chat-staging.example.com/api${NC}"
        echo -e "  API Docs: ${GREEN}https://tms-chat-staging.example.com/docs${NC}"
    fi

    echo -e "\nUseful commands:"
    echo -e "  View backend logs: ${YELLOW}sudo journalctl -u tms-backend -f${NC}"
    echo -e "  View frontend logs: ${YELLOW}sudo journalctl -u tms-frontend -f${NC}"
    echo -e "  View nginx logs: ${YELLOW}sudo tail -f /var/log/nginx/tms-$ENVIRONMENT-*.log${NC}"
}

# Main deployment flow
main() {
    # Check if running as correct user
    check_user

    # Ask for confirmation
    echo -e "${YELLOW}About to deploy to $ENVIRONMENT environment.${NC}"
    echo -e "${YELLOW}This will:${NC}"
    echo -e "  1. Pull latest code from Git"
    echo -e "  2. Install dependencies"
    echo -e "  3. Run database migrations"
    echo -e "  4. Build frontend"
    echo -e "  5. Restart services"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi

    # Deploy components
    deploy_backend
    deploy_frontend
    reload_nginx

    # Show summary
    show_summary
}

# Run main function
main
