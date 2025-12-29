#!/bin/bash

################################################################################
# Apache Airflow Setup Script
#
# This script automates the setup of Apache Airflow 2.6.0 with Google Cloud
# Provider support. It is idempotent and safe to run multiple times.
#
# Usage: ./setup_airflow.sh
#
# Supported platforms: macOS, Linux, Windows (with WSL2)
################################################################################

set -euo pipefail

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_NAME="airflow-venv"
AIRFLOW_VERSION="2.6.0"
GOOGLE_PROVIDER_VERSION="10.10.0"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="airflow"
ADMIN_EMAIL="admin@localhost"
AIRFLOW_HOME="${HOME}/airflow"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed or not in PATH"
        return 1
    fi
    return 0
}

# Function to safely activate venv
activate_venv() {
    if [ -d "$VENV_NAME" ]; then
        print_info "Activating virtual environment..."
        if [ -f "$VENV_NAME/bin/activate" ]; then
            source "$VENV_NAME/bin/activate"
            print_success "Virtual environment activated"
        else
            print_error "Virtual environment activation script not found"
            return 1
        fi
    fi
}

################################################################################
# Pre-flight Checks
################################################################################

print_header "Phase 1: Pre-flight Checks"

print_info "Checking system requirements..."

# Check Python
if ! check_command "python3"; then
    print_error "Python 3 is required but not installed."
    print_info "Install Python 3.9+ from: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python 3 found: $PYTHON_VERSION"

# Check pip
if ! check_command "pip3"; then
    print_error "pip3 is required but not installed."
    exit 1
fi

print_success "pip3 is available"

# Check if virtualenv module is available
if ! python3 -c "import venv" 2>/dev/null; then
    print_error "Python venv module is not available"
    print_info "Install it with: python3 -m pip install --upgrade pip"
    exit 1
fi

print_success "Python venv module is available"

print_success "All pre-flight checks passed!\n"

################################################################################
# Phase 2: Virtual Environment Setup
################################################################################

print_header "Phase 2: Virtual Environment Setup"

if [ -d "$VENV_NAME" ]; then
    print_warning "Virtual environment '$VENV_NAME' already exists"
    print_info "Reusing existing virtual environment..."
else
    print_info "Creating virtual environment: $VENV_NAME"
    python3 -m venv "$VENV_NAME"
    print_success "Virtual environment created"
fi

activate_venv || {
    print_error "Failed to activate virtual environment"
    exit 1
}

# Upgrade pip, setuptools, and wheel
print_info "Upgrading pip, setuptools, and wheel..."
python3 -m pip install --upgrade pip setuptools wheel --quiet
print_success "pip, setuptools, and wheel upgraded"

################################################################################
# Phase 3: Install Apache Airflow
################################################################################

print_header "Phase 3: Installing Apache Airflow and Dependencies"

print_info "Installing apache-airflow==$AIRFLOW_VERSION..."
pip install "apache-airflow==$AIRFLOW_VERSION" --quiet

if python3 -c "import airflow; print(airflow.__version__)" &>/dev/null; then
    INSTALLED_VERSION=$(python3 -c "import airflow; print(airflow.__version__)")
    print_success "Apache Airflow installed: $INSTALLED_VERSION"
else
    print_error "Failed to install Apache Airflow"
    exit 1
fi

################################################################################
# Phase 4: Install Google Cloud Provider
################################################################################

print_header "Phase 4: Installing Google Cloud Provider"

print_info "Installing apache-airflow-providers-google==$GOOGLE_PROVIDER_VERSION..."
pip install "apache-airflow-providers-google==$GOOGLE_PROVIDER_VERSION" --quiet

if python3 -c "from airflow.providers.google import __version__" 2>/dev/null; then
    print_success "Google Cloud Provider installed successfully"
else
    print_warning "Google Cloud Provider may require additional setup"
fi

################################################################################
# Phase 5: Initialize Airflow Database
################################################################################

print_header "Phase 5: Initialize Airflow Database"

# Set Airflow home if not already set
if [ -z "${AIRFLOW_HOME:-}" ]; then
    export AIRFLOW_HOME="$AIRFLOW_HOME"
    print_info "AIRFLOW_HOME set to: $AIRFLOW_HOME"
fi

# Create AIRFLOW_HOME if it doesn't exist
if [ ! -d "$AIRFLOW_HOME" ]; then
    mkdir -p "$AIRFLOW_HOME"
    print_info "Created AIRFLOW_HOME directory: $AIRFLOW_HOME"
fi

# Check if database is already initialized
if [ -f "$AIRFLOW_HOME/airflow.db" ]; then
    print_warning "Airflow database already exists at $AIRFLOW_HOME/airflow.db"
    print_info "Skipping database initialization to maintain idempotency"
else
    print_info "Initializing Airflow database..."
    airflow db init --quiet
    print_success "Airflow database initialized"
fi

################################################################################
# Phase 6: Create Admin User (Idempotent)
################################################################################

print_header "Phase 6: Create/Verify Admin User"

# Check if user already exists
if airflow users list | grep -q "$ADMIN_USERNAME"; then
    print_warning "Admin user '$ADMIN_USERNAME' already exists"
    print_info "Skipping user creation to maintain idempotency"
else
    print_info "Creating admin user: $ADMIN_USERNAME"
    airflow users create \
        --username "$ADMIN_USERNAME" \
        --password "$ADMIN_PASSWORD" \
        --email "$ADMIN_EMAIL" \
        --firstname Admin \
        --lastname User \
        --role Admin \
        2>/dev/null || {
        print_error "Failed to create admin user"
        exit 1
    }
    print_success "Admin user created: $ADMIN_USERNAME"
fi

print_info "Admin credentials:"
print_info "  Username: $ADMIN_USERNAME"
print_info "  Password: $ADMIN_PASSWORD"
print_info "  Email: $ADMIN_EMAIL"

################################################################################
# Phase 7: Verify Installation
################################################################################

print_header "Phase 7: Verification"

print_info "Verifying installation..."

# Check Airflow version
if python3 -c "import airflow" 2>/dev/null; then
    AIRFLOW_INSTALLED=$(python3 -c "import airflow; print(airflow.__version__)")
    print_success "Apache Airflow: $AIRFLOW_INSTALLED"
else
    print_error "Airflow import failed"
fi

# Check Google Provider
if python3 -c "from airflow.providers.google import __version__" 2>/dev/null; then
    print_success "Google Cloud Provider: installed"
else
    print_warning "Google Cloud Provider: not fully loaded"
fi

# Check Airflow home
if [ -d "$AIRFLOW_HOME" ]; then
    print_success "Airflow home: $AIRFLOW_HOME"
fi

# Check database
if [ -f "$AIRFLOW_HOME/airflow.db" ]; then
    print_success "Database initialized: $AIRFLOW_HOME/airflow.db"
fi

################################################################################
# Phase 8: Usage Instructions
################################################################################

print_header "Setup Complete!"

echo -e "${GREEN}Apache Airflow has been successfully set up!${NC}\n"

echo -e "${BLUE}Quick Start Guide:${NC}\n"

echo "1. Ensure the virtual environment is activated:"
echo -e "   ${YELLOW}source $VENV_NAME/bin/activate${NC}"

echo -e "\n2. Start Airflow Services:\n"

echo -e "   ${YELLOW}Option A: Start Scheduler and Webserver in background${NC}"
echo "   # Terminal 1: Start the Scheduler"
echo -e "   ${YELLOW}airflow scheduler${NC}"
echo ""
echo "   # Terminal 2: Start the Webserver"
echo -e "   ${YELLOW}airflow webserver --port 8080${NC}"

echo -e "\n   ${YELLOW}Option B: Start both services with a single command${NC}"
echo -e "   ${YELLOW}airflow standalone${NC}"
echo "   (This runs scheduler and webserver in one process - good for development)"

echo -e "\n3. Access the Airflow Web UI:"
echo -e "   ${YELLOW}http://localhost:8080${NC}"

echo -e "\n4. Login with credentials:"
echo -e "   ${YELLOW}Username: $ADMIN_USERNAME${NC}"
echo -e "   ${YELLOW}Password: $ADMIN_PASSWORD${NC}"

echo -e "\n${BLUE}Platform-Specific Instructions:${NC}\n"

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}macOS:${NC}"
    echo "  • Virtual environment activation:"
    echo -e "    ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo "  • To deactivate: ${YELLOW}deactivate${NC}"
    echo "  • Logs location: ~/airflow/logs/"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${YELLOW}Linux:${NC}"
    echo "  • Virtual environment activation:"
    echo -e "    ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo "  • To deactivate: ${YELLOW}deactivate${NC}"
    echo "  • Logs location: ~/airflow/logs/"
else
    echo -e "${YELLOW}Windows (WSL2):${NC}"
    echo "  • Virtual environment activation:"
    echo -e "    ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo "  • To deactivate: ${YELLOW}deactivate${NC}"
    echo "  • Logs location: ~/airflow/logs/"
    echo ""
    echo -e "${YELLOW}Windows (Native):${NC}"
    echo "  • Virtual environment activation (PowerShell):"
    echo -e "    ${YELLOW}.\\$VENV_NAME\\Scripts\\Activate.ps1${NC}"
    echo "  • Virtual environment activation (Command Prompt):"
    echo -e "    ${YELLOW}$VENV_NAME\\Scripts\\activate.bat${NC}"
    echo "  • To deactivate: ${YELLOW}deactivate${NC}"
    echo "  • Logs location: %USERPROFILE%\\airflow\\logs\\"
fi

echo -e "\n${BLUE}Additional Commands:${NC}\n"

echo "  List all users:"
echo -e "    ${YELLOW}airflow users list${NC}"

echo "\n  Reset admin password:"
echo -e "    ${YELLOW}airflow users create --username admin --password newpassword --email admin@localhost --role Admin --firstname Admin --lastname User${NC}"

echo "\n  View Airflow configuration:"
echo -e "    ${YELLOW}airflow config list${NC}"

echo "\n  Run DAG tests:"
echo -e "    ${YELLOW}airflow dags test [dag_id]${NC}"

echo -e "\n${BLUE}Environment:${NC}\n"
echo "  AIRFLOW_HOME: $AIRFLOW_HOME"
echo "  Python: $(python3 --version)"
echo "  Airflow version: $(python3 -c 'import airflow; print(airflow.__version__)' 2>/dev/null || echo 'unknown')"

echo -e "\n${BLUE}Troubleshooting:${NC}\n"

echo "  If port 8080 is already in use:"
echo -e "    ${YELLOW}airflow webserver --port 8081${NC}"

echo "\n  To reset everything and start fresh:"
echo -e "    ${YELLOW}rm -rf airflow-venv ~/airflow${NC}"
echo -e "    ${YELLOW}./setup_airflow.sh${NC}"

echo "\n  For issues with dependencies, upgrade pip:"
echo -e "    ${YELLOW}python3 -m pip install --upgrade pip${NC}"

echo -e "\n${GREEN}Happy DAG scheduling! 🚀${NC}\n"

# Save script completion info
COMPLETION_FILE="$AIRFLOW_HOME/.setup_complete"
echo "Setup completed at $(date)" > "$COMPLETION_FILE"
print_success "Setup completion marker saved: $COMPLETION_FILE"

# Deactivate venv if we activated it
if [ ! -z "${VIRTUAL_ENV:-}" ]; then
    print_info "Virtual environment will remain active in your shell"
    print_info "To deactivate when finished, run: deactivate"
fi

exit 0

