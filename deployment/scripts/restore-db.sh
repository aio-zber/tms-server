#!/bin/bash
# Database Restore Script for TMS
# Usage: ./restore-db.sh <backup_file> [staging|production]

set -e  # Exit on error

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Error: Backup file not specified"
    echo "Usage: ./restore-db.sh <backup_file> [staging|production]"
    echo ""
    echo "Available backups:"
    ls -lh /home/tmsapp/backups/database/*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE=$1
ENVIRONMENT=${2:-staging}

# Validate backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

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

echo "========================================="
echo "TMS Database Restore"
echo "========================================="
echo "WARNING: This will OVERWRITE the $ENVIRONMENT database!"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Database: $DB_NAME"
echo "Backup file: $BACKUP_FILE"
echo "========================================="

# Confirmation prompt
read -p "Are you ABSOLUTELY sure you want to restore? (type 'yes' to continue): " -r
echo

if [[ ! $REPLY == "yes" ]]; then
    echo "Restore cancelled"
    exit 1
fi

# Additional confirmation for production
if [[ "$ENVIRONMENT" == "production" ]]; then
    echo ""
    echo "WARNING: You are about to restore the PRODUCTION database!"
    read -p "Type 'RESTORE PRODUCTION' to confirm: " -r
    echo

    if [[ ! $REPLY == "RESTORE PRODUCTION" ]]; then
        echo "Restore cancelled"
        exit 1
    fi
fi

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Stop backend service
echo "Stopping backend service..."
sudo systemctl stop tms-backend

# Wait for connections to close
sleep 3

# Terminate existing connections
echo "Terminating existing database connections..."
psql -h "$DB_HOST" \
     -p "$DB_PORT" \
     -U "$DB_USER" \
     -d postgres \
     -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"

# Drop and recreate database
echo "Dropping and recreating database..."
psql -h "$DB_HOST" \
     -p "$DB_PORT" \
     -U "$DB_USER" \
     -d postgres \
     -c "DROP DATABASE IF EXISTS $DB_NAME;"

psql -h "$DB_HOST" \
     -p "$DB_PORT" \
     -U "$DB_USER" \
     -d postgres \
     -c "CREATE DATABASE $DB_NAME WITH OWNER = $DB_USER ENCODING = 'UTF8';"

# Restore backup
echo "Restoring backup..."
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" \
                                 -p "$DB_PORT" \
                                 -U "$DB_USER" \
                                 -d "$DB_NAME" \
                                 --quiet

# Unset password
unset PGPASSWORD

# Run migrations to ensure schema is up to date
echo "Running database migrations..."
cd /home/tmsapp/tms-server
source venv/bin/activate
alembic upgrade head
deactivate

# Start backend service
echo "Starting backend service..."
sudo systemctl start tms-backend

# Wait for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet tms-backend; then
    echo "✓ Backend service is running"
else
    echo "✗ Backend service failed to start"
    sudo systemctl status tms-backend
    exit 1
fi

echo ""
echo "========================================="
echo "Database restore completed successfully"
echo "========================================="
