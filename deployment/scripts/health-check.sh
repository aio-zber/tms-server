#!/bin/bash
#
# TMS Health Check Script
# Monitors critical services and alerts if issues detected
#
# Installation:
#   chmod +x deployment/scripts/health-check.sh
#   sudo crontab -e
#   Add: */5 * * * * /home/tmsapp/tms-server/deployment/scripts/health-check.sh >> /var/log/tms-health.log 2>&1
#
# Usage:
#   ./deployment/scripts/health-check.sh
#

set -euo pipefail

# Configuration
LOG_PREFIX="[TMS-HEALTH]"
ALERT_EMAIL="${ALERT_EMAIL:-}"  # Set via env var if email alerts needed
RESTART_ON_FAILURE="${RESTART_ON_FAILURE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if a service is running
check_service() {
    local service=$1
    local port=$2
    local url=$3
    local status_ok=true

    log "Checking ${service}..."

    # Check systemd status
    if ! systemctl is-active --quiet "${service}"; then
        log "${RED}ERROR: ${service} is not running${NC}"
        status_ok=false

        if [ "${RESTART_ON_FAILURE}" = "true" ]; then
            log "${YELLOW}Attempting to restart ${service}...${NC}"
            systemctl restart "${service}"
            sleep 5

            if systemctl is-active --quiet "${service}"; then
                log "${GREEN}Successfully restarted ${service}${NC}"
                status_ok=true
            else
                log "${RED}Failed to restart ${service}${NC}"
            fi
        fi
    else
        log "${GREEN}OK: ${service} is running${NC}"
    fi

    # Check if port is listening
    if ! nc -z localhost "${port}" 2>/dev/null; then
        log "${RED}ERROR: ${service} not listening on port ${port}${NC}"
        status_ok=false
    else
        log "${GREEN}OK: ${service} listening on port ${port}${NC}"
    fi

    # Check HTTP endpoint if provided
    if [ -n "${url}" ]; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "${url}" 2>/dev/null || echo "000")
        if [ "${http_code}" = "200" ] || [ "${http_code}" = "307" ] || [ "${http_code}" = "404" ]; then
            log "${GREEN}OK: ${service} HTTP endpoint responsive (${http_code})${NC}"
        else
            log "${RED}ERROR: ${service} HTTP endpoint returned ${http_code}${NC}"
            status_ok=false
        fi
    fi

    # Return status
    if [ "${status_ok}" = "true" ]; then
        return 0
    else
        return 1
    fi
}

# Check disk space
check_disk_space() {
    log "Checking disk space..."

    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "${usage}" -gt 90 ]; then
        log "${RED}ERROR: Disk usage is ${usage}% (critical)${NC}"
        return 1
    elif [ "${usage}" -gt 80 ]; then
        log "${YELLOW}WARNING: Disk usage is ${usage}% (high)${NC}"
        return 0
    else
        log "${GREEN}OK: Disk usage is ${usage}%${NC}"
        return 0
    fi
}

# Check memory usage
check_memory() {
    log "Checking memory..."

    local mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')

    if [ "${mem_usage}" -gt 90 ]; then
        log "${RED}ERROR: Memory usage is ${mem_usage}% (critical)${NC}"
        return 1
    elif [ "${mem_usage}" -gt 80 ]; then
        log "${YELLOW}WARNING: Memory usage is ${mem_usage}% (high)${NC}"
        return 0
    else
        log "${GREEN}OK: Memory usage is ${mem_usage}%${NC}"
        return 0
    fi
}

# Check for zombie processes
check_zombies() {
    log "Checking for zombie processes..."

    local zombie_count=$(ps aux | awk '$8=="Z" {print $0}' | wc -l)

    if [ "${zombie_count}" -gt 0 ]; then
        log "${YELLOW}WARNING: Found ${zombie_count} zombie process(es)${NC}"
        ps aux | awk '$8=="Z" {print $0}' | while read line; do
            log "  Zombie: $line"
        done
        return 1
    else
        log "${GREEN}OK: No zombie processes${NC}"
        return 0
    fi
}

# Main health check
main() {
    log "========================================="
    log "Starting TMS Health Check"
    log "========================================="

    local all_healthy=true

    # Check backend service
    if ! check_service "tms-backend" 8000 "http://localhost:8000/docs"; then
        all_healthy=false
    fi

    echo ""

    # Check frontend service
    if ! check_service "tms-frontend" 3000 "http://localhost:3000"; then
        all_healthy=false
    fi

    echo ""

    # Check nginx
    if ! check_service "nginx" 80 "http://localhost"; then
        all_healthy=false
    fi

    echo ""

    # Check system resources
    if ! check_disk_space; then
        all_healthy=false
    fi

    echo ""

    if ! check_memory; then
        all_healthy=false
    fi

    echo ""

    # Check for zombie processes
    check_zombies || true  # Don't fail overall health check for zombies

    echo ""

    # Final status
    log "========================================="
    if [ "${all_healthy}" = "true" ]; then
        log "${GREEN}Overall Status: HEALTHY${NC}"
        log "========================================="
        exit 0
    else
        log "${RED}Overall Status: UNHEALTHY${NC}"
        log "========================================="

        # Send alert if configured
        if [ -n "${ALERT_EMAIL}" ]; then
            echo "TMS Health Check FAILED at $(date)" | \
                mail -s "TMS Health Check Alert" "${ALERT_EMAIL}"
        fi

        exit 1
    fi
}

# Run main function
main
