#!/bin/bash
#
# TMS Improved Deployment Script
# Handles deployment with proper process cleanup and verification
#
# Usage:
#   ./deployment/scripts/deploy-improved.sh [staging|production]
#

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="/home/tmsapp/tms-server"
CLIENT_DIR="/home/tmsapp/tms-client"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${BLUE}[DEPLOY]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if running as tmsapp user
check_user() {
    if [ "$(whoami)" != "tmsapp" ] && [ "$(whoami)" != "root" ]; then
        error "This script must be run as tmsapp or root user"
        exit 1
    fi
}

# Validate environment
validate_environment() {
    if [ "${ENVIRONMENT}" != "staging" ] && [ "${ENVIRONMENT}" != "production" ]; then
        error "Invalid environment: ${ENVIRONMENT}"
        error "Usage: $0 [staging|production]"
        exit 1
    fi

    log "Deploying to: ${ENVIRONMENT}"
}

# Stop services cleanly
stop_services() {
    log "Stopping services..."

    # Stop systemd services
    systemctl stop tms-frontend || warning "tms-frontend already stopped"
    systemctl stop tms-backend || warning "tms-backend already stopped"

    # Wait for services to stop
    sleep 3

    # Kill any remaining zombie processes
    log "Cleaning up zombie processes..."
    pkill -9 -u tmsapp -f "next-server" || true
    pkill -9 -u tmsapp -f "uvicorn" || true

    # Wait for ports to be free
    log "Waiting for ports to be freed..."
    sleep 5

    # Verify ports are free
    if lsof -i :3000 >/dev/null 2>&1; then
        warning "Port 3000 still in use, forcing cleanup..."
        fuser -k 3000/tcp || true
        sleep 2
    fi

    if lsof -i :8000 >/dev/null 2>&1; then
        warning "Port 8000 still in use, forcing cleanup..."
        fuser -k 8000/tcp || true
        sleep 2
    fi

    success "Services stopped and processes cleaned up"
}

# Backup current deployment
backup_deployment() {
    log "Creating backup..."

    local backup_dir="/home/tmsapp/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${backup_dir}"

    # Backup server
    if [ -d "${SERVER_DIR}" ]; then
        tar -czf "${backup_dir}/tms-server.tar.gz" \
            -C "${SERVER_DIR}" \
            --exclude=venv \
            --exclude=__pycache__ \
            --exclude=.git \
            . 2>/dev/null || warning "Server backup had warnings"
    fi

    # Backup client
    if [ -d "${CLIENT_DIR}" ]; then
        tar -czf "${backup_dir}/tms-client.tar.gz" \
            -C "${CLIENT_DIR}" \
            --exclude=node_modules \
            --exclude=.next \
            --exclude=.git \
            . 2>/dev/null || warning "Client backup had warnings"
    fi

    success "Backup created at: ${backup_dir}"
}

# Pull latest code
update_code() {
    log "Pulling latest code..."

    # Update server
    log "Updating server repository..."
    cd "${SERVER_DIR}"
    git fetch origin
    git pull origin "${ENVIRONMENT}"

    # Update client
    log "Updating client repository..."
    cd "${CLIENT_DIR}"
    git fetch origin
    git pull origin "${ENVIRONMENT}"

    success "Code updated"
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."

    # Backend dependencies
    log "Installing backend dependencies..."
    cd "${SERVER_DIR}"
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    # Frontend dependencies
    log "Installing frontend dependencies..."
    cd "${CLIENT_DIR}"
    npm ci --production=false

    success "Dependencies installed"
}

# Build frontend
build_frontend() {
    log "Building frontend..."

    cd "${CLIENT_DIR}"

    # Clean previous build
    rm -rf .next

    # Build
    npm run build

    success "Frontend built successfully"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."

    cd "${SERVER_DIR}"
    source venv/bin/activate

    # Check migration status
    alembic current

    # Run migrations
    alembic upgrade head

    success "Database migrations completed"
}

# Start services
start_services() {
    log "Starting services..."

    # Start backend
    log "Starting backend..."
    systemctl start tms-backend
    sleep 5

    # Verify backend started
    if ! systemctl is-active --quiet tms-backend; then
        error "Backend failed to start"
        journalctl -u tms-backend -n 50 --no-pager
        exit 1
    fi

    # Start frontend
    log "Starting frontend..."
    systemctl start tms-frontend
    sleep 5

    # Verify frontend started
    if ! systemctl is-active --quiet tms-frontend; then
        error "Frontend failed to start"
        journalctl -u tms-frontend -n 50 --no-pager
        exit 1
    fi

    # Reload nginx
    log "Reloading nginx..."
    systemctl reload nginx

    success "All services started"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."

    # Check backend
    local backend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs || echo "000")
    if [ "${backend_status}" = "200" ]; then
        success "Backend is responding"
    else
        error "Backend health check failed (HTTP ${backend_status})"
        return 1
    fi

    # Check frontend
    local frontend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "000")
    if [ "${frontend_status}" = "200" ]; then
        success "Frontend is responding"
    else
        error "Frontend health check failed (HTTP ${frontend_status})"
        return 1
    fi

    # Check nginx
    local nginx_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost || echo "000")
    if [ "${nginx_status}" = "200" ] || [ "${nginx_status}" = "307" ]; then
        success "Nginx is responding"
    else
        warning "Nginx health check returned HTTP ${nginx_status}"
    fi

    success "Deployment verification passed"
}

# Show service status
show_status() {
    log "Service Status:"
    echo ""
    systemctl status tms-backend tms-frontend nginx --no-pager || true
    echo ""
}

# Main deployment flow
main() {
    log "========================================="
    log "TMS Deployment Script"
    log "========================================="

    check_user
    validate_environment

    echo ""
    log "Phase 1: Preparation"
    log "-------------------"
    backup_deployment

    echo ""
    log "Phase 2: Service Shutdown"
    log "------------------------"
    stop_services

    echo ""
    log "Phase 3: Code Update"
    log "-------------------"
    update_code

    echo ""
    log "Phase 4: Dependencies"
    log "-------------------"
    install_dependencies

    echo ""
    log "Phase 5: Build Frontend"
    log "---------------------"
    build_frontend

    echo ""
    log "Phase 6: Database Migrations"
    log "--------------------------"
    run_migrations

    echo ""
    log "Phase 7: Service Startup"
    log "----------------------"
    start_services

    echo ""
    log "Phase 8: Verification"
    log "-------------------"
    if verify_deployment; then
        echo ""
        log "========================================="
        success "Deployment completed successfully!"
        log "========================================="
        show_status
        exit 0
    else
        echo ""
        log "========================================="
        error "Deployment verification failed!"
        log "========================================="
        error "Check logs with: journalctl -u tms-backend -f"
        error "              or: journalctl -u tms-frontend -f"
        exit 1
    fi
}

# Run main deployment
main
