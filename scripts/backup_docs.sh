#!/bin/bash
# =============================================================================
# Backup Script for Documentation
# =============================================================================
# Creates a compressed backup of the docs folder
#
# Usage: ./scripts/backup_docs.sh [destination_dir]
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="${1:-/Users/josepharuja/Documents/projects/jsr}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="docs-backup-${TIMESTAMP}.tar.gz"

echo "=============================================="
echo "  Documentation Backup"
echo "=============================================="
echo "Source:  $PROJECT_DIR/docs"
echo "Dest:    $DEST_DIR/$BACKUP_NAME"
echo "=============================================="
echo ""

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Create backup
echo -e "${YELLOW}Creating docs backup...${NC}"
cd "$PROJECT_DIR"

tar -czf "$DEST_DIR/$BACKUP_NAME" docs/

# Show result
echo ""
echo -e "${GREEN}✅ Docs backup created successfully!${NC}"
echo ""
ls -lh "$DEST_DIR/$BACKUP_NAME"
echo ""
echo "Contents:"
tar -tzf "$DEST_DIR/$BACKUP_NAME" | head -10
echo "..."
echo ""
echo "To restore:"
echo "  tar -xzf $DEST_DIR/$BACKUP_NAME -C /path/to/restore"

