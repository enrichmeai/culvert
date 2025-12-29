#!/bin/bash

# LOA Blueprint - Build Script (macOS/Linux)
# This script provides a simple entry point for common tasks.

set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${BLUE}LOA Blueprint Build Script${NC}"
    echo "Usage: ./build.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup   - Create virtual environment and install dependencies"
    echo "  start   - Start local Docker services"
    echo "  stop    - Stop local Docker services"
    echo "  test    - Run all tests"
    echo "  clean   - Remove temporary files and virtual environment"
    echo "  help    - Show this help message"
}

case "$1" in
    setup)
        echo -e "${BLUE}Setting up environment...${NC}"
        make setup
        echo -e "${GREEN}Setup complete!${NC}"
        ;;
    start)
        echo -e "${BLUE}Starting services...${NC}"
        make start
        ;;
    stop)
        echo -e "${BLUE}Stopping services...${NC}"
        make stop
        ;;
    test)
        echo -e "${BLUE}Running tests...${NC}"
        make test
        ;;
    clean)
        echo -e "${BLUE}Cleaning up...${NC}"
        make clean
        ;;
    help|*)
        show_help
        ;;
esac
