#!/bin/bash
# Database Backup Script for TMS
# Usage: ./backup-db.sh [staging|production]

set -e  # Exit on error

# Configuration
ENVIRONMENT=${1:-production}
BACKUP_DIR="/home/tmsapp/backups/database"
RETENTION_DAYS=30

# Database credentials
DB_HOST="localhost"
DB_PORT="5432"
DB_USER="postgres"
DB_PASSWORD="REDACTED_DB_PASSWORD"

# Determine database name
if [[ "$ENVIRONMENT" == "production" ]]; then
    DB_NAME="tms_production_db"
else
    DB_NAME="tms_staging_db"
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "========================================="
echo "TMS Database Backup"
echo "========================================="
echo "Environment: $ENVIRONMENT"
echo "Database: $DB_NAME"
echo "Backup file: $BACKUP_FILE"
echo "========================================="

# Export password for pg_dump
export PGPASSWORD="$DB_PASSWORD"

# Perform backup
echo "Starting backup..."
pg_dump -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --format=plain \
        --no-owner \
        --no-acl \
        | gzip > "$BACKUP_FILE"

# Unset password
unset PGPASSWORD

# Check if backup was successful
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✓ Backup completed successfully"
    echo "  File: $BACKUP_FILE"
    echo "  Size: $BACKUP_SIZE"
else
    echo "✗ Backup failed!"
    exit 1
fi

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
echo "✓ Old backups cleaned up"

# List recent backups
echo ""
echo "Recent backups:"
ls -lh "$BACKUP_DIR" | tail -n 10

# Upload to Alibaba Cloud OSS (optional - uncomment if you want to use OSS for backups)
# echo "Uploading to OSS..."
# ossutil cp "$BACKUP_FILE" oss://tms-oss-goli/backups/database/

echo ""
echo "========================================="
echo "Backup process completed"
echo "========================================="
