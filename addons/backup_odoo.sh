#!/bin/bash

# Odoo Backup Script
# Creates full backup of database, addons, and filestore

# Configuration
DB_NAME="saqifaa1-main-22150152_2025-12-15_191334_test_fs"
DB_USER="odoo"
DB_HOST="localhost"
DB_PORT="5432"
ADDONS_PATH="/Users/mostafa/ odoo-18/saqifaa1-staging"
FILESTORE_PATH="$HOME/.local/share/Odoo/filestore/$DB_NAME"
BACKUP_BASE_DIR="$HOME/odoo_backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/backup_$TIMESTAMP"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Odoo Full Backup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create backup directory
echo -e "${GREEN}[1/5] Creating backup directory...${NC}"
mkdir -p "$BACKUP_DIR"
echo "✓ Directory created: $BACKUP_DIR"
echo ""

# Backup database
echo -e "${GREEN}[2/5] Backing up database: $DB_NAME${NC}"
if command -v pg_dump &> /dev/null; then
    pg_dump -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" > "$BACKUP_DIR/database.sql" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        DB_SIZE=$(du -sh "$BACKUP_DIR/database.sql" | cut -f1)
        echo "✓ Database backup completed: $DB_SIZE"
    else
        echo -e "${RED}⚠ Database backup failed (might need password or permissions)${NC}"
        echo "  You can backup manually from Odoo UI: http://localhost:8069/web/database/manager"
    fi
else
    echo -e "${RED}⚠ pg_dump not found, skipping database backup${NC}"
    echo "  Install PostgreSQL client or backup from Odoo UI"
fi
echo ""

# Backup addons
echo -e "${GREEN}[3/5] Backing up custom addons...${NC}"
if [ -d "$ADDONS_PATH" ]; then
    cp -r "$ADDONS_PATH" "$BACKUP_DIR/addons"
    ADDONS_SIZE=$(du -sh "$BACKUP_DIR/addons" | cut -f1)
    echo "✓ Addons backup completed: $ADDONS_SIZE"
    echo "  Modules backed up:"
    ls -1 "$BACKUP_DIR/addons" | grep -v ".DS_Store" | sed 's/^/    - /'
else
    echo -e "${RED}⚠ Addons path not found: $ADDONS_PATH${NC}"
fi
echo ""

# Backup filestore
echo -e "${GREEN}[4/5] Backing up filestore...${NC}"
if [ -d "$FILESTORE_PATH" ]; then
    cp -r "$FILESTORE_PATH" "$BACKUP_DIR/filestore"
    FILESTORE_SIZE=$(du -sh "$BACKUP_DIR/filestore" | cut -f1)
    echo "✓ Filestore backup completed: $FILESTORE_SIZE"
else
    echo "ℹ Filestore not found (might be empty or different location)"
fi
echo ""

# Create compressed archive
echo -e "${GREEN}[5/5] Creating compressed archive...${NC}"
cd "$BACKUP_BASE_DIR"
tar -czf "backup_$TIMESTAMP.tar.gz" "backup_$TIMESTAMP" 2>/dev/null

if [ $? -eq 0 ]; then
    ARCHIVE_SIZE=$(du -sh "backup_$TIMESTAMP.tar.gz" | cut -f1)
    echo "✓ Archive created: backup_$TIMESTAMP.tar.gz ($ARCHIVE_SIZE)"
    
    # Remove uncompressed directory to save space
    rm -rf "backup_$TIMESTAMP"
    echo "✓ Cleanup completed"
else
    echo -e "${RED}⚠ Archive creation failed, keeping uncompressed backup${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Backup Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Backup location: $BACKUP_BASE_DIR"
if [ -f "$BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz" ]; then
    echo "Archive: backup_$TIMESTAMP.tar.gz"
    TOTAL_SIZE=$(du -sh "$BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz" | cut -f1)
else
    echo "Directory: backup_$TIMESTAMP/"
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
fi
echo "Total size: $TOTAL_SIZE"
echo "Timestamp: $TIMESTAMP"
echo ""
echo -e "${GREEN}✓ Backup completed successfully!${NC}"
echo ""

# Optional: Keep only last 5 backups
echo "Checking old backups..."
BACKUP_COUNT=$(ls -1 "$BACKUP_BASE_DIR"/backup_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 5 ]; then
    echo "Found $BACKUP_COUNT backups, keeping only the last 5..."
    ls -1t "$BACKUP_BASE_DIR"/backup_*.tar.gz | tail -n +6 | xargs rm -f
    echo "✓ Old backups cleaned up"
fi

echo ""
echo "To restore this backup, run:"
echo "  tar -xzf $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz -C $BACKUP_BASE_DIR"
echo ""
