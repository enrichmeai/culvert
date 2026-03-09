#!/bin/bash
# =============================================================================
# Backup Script for legacy-migration-reference project
# =============================================================================
# Creates a compressed backup excluding virtual environments and cache files
#
# Usage: ./scripts/backup_project.sh [destination_dir]
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="legacy-migration-reference"
DEST_DIR="${1:-$HOME/backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="${PROJECT_NAME}-backup-${TIMESTAMP}.tar.gz"

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

echo "=============================================="
echo "  Project Backup"
echo "=============================================="
echo "Project: $PROJECT_NAME"
echo "Source:  $PROJECT_DIR"
echo "Dest:    $DEST_DIR/$BACKUP_NAME"
echo "=============================================="
echo ""

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
cd "$(dirname "$PROJECT_DIR")"

tar --exclude='venv*' \
    --exclude='.venv*' \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.terraform' \
    --exclude='*.egg-info' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.DS_Store' \
    -czf "$DEST_DIR/$BACKUP_NAME" \
    "$PROJECT_NAME"

# Show result
echo ""
echo -e "${GREEN}✅ Backup created successfully!${NC}"
echo ""
ls -lh "$DEST_DIR/$BACKUP_NAME"
echo ""
echo "To restore:"
echo "  tar -xzf $DEST_DIR/$BACKUP_NAME -C /path/to/restore"

