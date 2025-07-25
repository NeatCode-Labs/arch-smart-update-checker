#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installation script for Arch Smart Update Checker (ASUC)
# 
# This script handles installation of ASUC and its dependencies across different scenarios:
# - System-wide installation
# - User-specific installation  
# - Virtual environment installation
# - Dependency checking and validation

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_NAME="asuc_venv"
REQUIRED_PYTHON_VERSION="3.8"

# Python dependencies from pyproject.toml
PYTHON_DEPS=(
    "requests>=2.25.0"
    "feedparser>=6.0.0" 
    "colorama>=0.4.0"
    "psutil>=5.8.0"
)

# System dependencies for Arch Linux and derivatives
ARCH_DEPS=("python" "python-pip" "tk" "polkit")

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")  echo -e "${BLUE}[INFO]${NC} $message" >&2 ;;
        "WARN")  echo -e "${YELLOW}[WARN]${NC} $message" >&2 ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
        "SUCCESS") echo -e "${GREEN}[SUCCESS]${NC} $message" >&2 ;;
        "STEP") echo -e "${PURPLE}[STEP]${NC} $message" >&2 ;;
    esac
}

# Error handling
error_exit() {
    log "ERROR" "$1"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Validate Python version
check_python_version() {
    local python_cmd="$1"
    local version_output
    
    if ! version_output=$($python_cmd --version 2>&1); then
        return 1
    fi
    
    local python_version=$(echo "$version_output" | grep -oE '[0-9]+\.[0-9]+' | head -1)
    
    if [[ -z "$python_version" ]]; then
        return 1
    fi
    
    # Compare versions (simplified - assumes format X.Y)
    local major=$(echo "$python_version" | cut -d. -f1)
    local minor=$(echo "$python_version" | cut -d. -f2)
    local req_major=$(echo "$REQUIRED_PYTHON_VERSION" | cut -d. -f1)
    local req_minor=$(echo "$REQUIRED_PYTHON_VERSION" | cut -d. -f2)
    
    if [[ $major -gt $req_major ]] || [[ $major -eq $req_major && $minor -ge $req_minor ]]; then
        echo "$python_version"
        return 0
    else
        return 1
    fi
}

# Detect Linux distribution
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    elif [[ -f /etc/arch-release ]]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

# Check system dependencies
check_system_deps() {
    log "STEP" "Checking system dependencies..."
    
    local distro=$(detect_distro)
    local missing_deps=()
    
    case "$distro" in
        "arch"|"manjaro"|"endeavouros"|"arcolinux"|"artix"|"blackarch"|"garuda")
            for dep in "${ARCH_DEPS[@]}"; do
                if ! pacman -Qi "$dep" >/dev/null 2>&1; then
                    missing_deps+=("$dep")
                fi
            done
            ;;
        *)
            error_exit "This application is designed for Arch Linux and its derivatives only. Detected distribution: $distro"
            ;;
    esac
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log "ERROR" "Missing system dependencies: ${missing_deps[*]}"
        log "INFO" "These dependencies are required for ASUC to function properly."
        log "INFO" ""
        
        # Ask user if they want to install missing dependencies
        echo -n "Would you like to install missing system dependencies now? [Y/n]: " >&2
        read -r response
        
        case "${response,,}" in
            n|no)
                log "ERROR" "Cannot continue without required system dependencies"
                log "INFO" "Install manually with: sudo pacman -S ${missing_deps[*]}"
                return 1
                ;;
            *)
                log "INFO" "Installing system dependencies: ${missing_deps[*]}"
                if sudo pacman -S --needed --noconfirm "${missing_deps[@]}"; then
                    log "SUCCESS" "System dependencies installed successfully"
                else
                    log "ERROR" "Failed to install system dependencies"
                    log "INFO" "Please install manually with: sudo pacman -S ${missing_deps[*]}"
                    return 1
                fi
                ;;
        esac
    fi
    
    log "SUCCESS" "All system dependencies are installed"
    return 0
}

# Find Python executable
find_python() {
    local python_candidates=("python3" "python" "python3.12" "python3.11" "python3.10" "python3.9" "python3.8")
    
    for python_cmd in "${python_candidates[@]}"; do
        if command_exists "$python_cmd"; then
            local version
            if version=$(check_python_version "$python_cmd"); then
                log "SUCCESS" "Found Python $version at $(command -v "$python_cmd")"
                echo "$python_cmd"
                return 0
            fi
        fi
    done
    
    log "ERROR" "Python $REQUIRED_PYTHON_VERSION or higher not found"
    return 1
}

# Check if we're in a virtual environment
in_virtual_env() {
    [[ -n "${VIRTUAL_ENV:-}" ]] || [[ -n "${CONDA_DEFAULT_ENV:-}" ]]
}

# Install Python dependencies
install_python_deps() {
    local python_cmd="$1"
    local install_type="$2"  # "user", "system", or "venv"
    
    log "STEP" "Installing Python dependencies ($install_type)..."
    
    # Check if pip is available
    if ! "$python_cmd" -m pip --version >/dev/null 2>&1; then
        error_exit "pip is not available. Please install python-pip package."
    fi
    
    # Check for externally managed environment (PEP 668)
    local externally_managed=false
    local python_version=$("$python_cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ -f "/usr/lib/python${python_version}/EXTERNALLY-MANAGED" ]]; then
        externally_managed=true
        log "WARN" "Python environment is externally managed (PEP 668)"
    fi
    
    # Prepare pip command
    local pip_args=()
    case "$install_type" in
        "user")
            pip_args+=("--user")
            if [[ "$externally_managed" == "true" ]]; then
                log "INFO" "Adding --break-system-packages flag for externally managed Python"
                pip_args+=("--break-system-packages")
            fi
            ;;
        "system")
            # System-wide installation (requires sudo)
            if [[ $EUID -ne 0 ]]; then
                error_exit "System-wide installation requires sudo privileges"
            fi
            if [[ "$externally_managed" == "true" ]]; then
                pip_args+=("--break-system-packages")
            fi
            ;;
        "venv")
            # Virtual environment - no special flags needed
            ;;
        *)
            error_exit "Invalid installation type: $install_type"
            ;;
    esac
    
    # Install dependencies
    for dep in "${PYTHON_DEPS[@]}"; do
        log "INFO" "Installing $dep..."
        if ! "$python_cmd" -m pip install "${pip_args[@]}" "$dep"; then
            error_exit "Failed to install $dep"
        fi
    done
    
    log "SUCCESS" "All Python dependencies installed successfully"
}

# Create virtual environment
create_venv() {
    local python_cmd="$1"
    local venv_path="$SCRIPT_DIR/$VENV_NAME"
    
    log "STEP" "Creating virtual environment at $venv_path..."
    
    if [[ -d "$venv_path" ]]; then
        log "WARN" "Virtual environment already exists. Removing..."
        rm -rf "$venv_path"
    fi
    
    if ! "$python_cmd" -m venv "$venv_path"; then
        error_exit "Failed to create virtual environment"
    fi
    
    log "SUCCESS" "Virtual environment created successfully"
    echo "$venv_path"
}

# Setup executable scripts
setup_executables() {
    local python_path="$1"
    
    log "STEP" "Setting up executable scripts..."
    
    # Make scripts executable
    chmod +x "$SCRIPT_DIR/asuc-gui" "$SCRIPT_DIR/asuc-cli"
    
    # If using virtual environment, create wrapper scripts
    if [[ "$python_path" == *"$VENV_NAME"* ]]; then
        local venv_path="$(dirname "$(dirname "$python_path")")"
        
        # Create wrapper script for GUI
        cat > "$SCRIPT_DIR/asuc-gui-venv" << EOF
#!/bin/bash
# Virtual environment wrapper for asuc-gui
source "$venv_path/bin/activate"
exec "$SCRIPT_DIR/asuc-gui" "\$@"
EOF
        chmod +x "$SCRIPT_DIR/asuc-gui-venv"
        
        # Create wrapper script for CLI
        cat > "$SCRIPT_DIR/asuc-cli-venv" << EOF
#!/bin/bash
# Virtual environment wrapper for asuc-cli
source "$venv_path/bin/activate"
exec "$SCRIPT_DIR/asuc-cli" "\$@"
EOF
        chmod +x "$SCRIPT_DIR/asuc-cli-venv"
        
        log "INFO" "Virtual environment wrapper scripts created:"
        log "INFO" "  GUI: $SCRIPT_DIR/asuc-gui-venv"
        log "INFO" "  CLI: $SCRIPT_DIR/asuc-cli-venv"
    fi
    
    log "SUCCESS" "Executable scripts are ready"
}

# Verify installation
verify_installation() {
    local python_cmd="$1"
    
    log "STEP" "Verifying installation..."
    
    # Check if all dependencies can be imported
    for dep in "requests" "feedparser" "colorama" "psutil" "tkinter"; do
        if ! "$python_cmd" -c "import $dep" 2>/dev/null; then
            log "ERROR" "Failed to import $dep"
            return 1
        fi
    done
    
    log "SUCCESS" "All dependencies verified successfully"
    return 0
}

# Display usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Install Arch Smart Update Checker and its dependencies.

OPTIONS:
    --user          Install Python packages for current user only (default)
    --system        Install Python packages system-wide (requires sudo)
    --venv          Create and use virtual environment
    --check-only    Only check dependencies, don't install
    --help          Show this help message

EXAMPLES:
    $0                    # Install with user packages (recommended)
    $0 --venv            # Install in virtual environment
    sudo $0 --system    # Install system-wide packages
    $0 --check-only     # Check dependencies without installing

EOF
}

# Main installation function
main() {
    local install_mode="user"
    local check_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --user)
                install_mode="user"
                shift
                ;;
            --system)
                install_mode="system"
                shift
                ;;
            --venv)
                install_mode="venv"
                shift
                ;;
            --check-only)
                check_only=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    log "INFO" "Starting ASUC installation..."
    log "INFO" "Installation mode: $install_mode"
    
    # Check if we're already in a virtual environment
    if in_virtual_env && [[ "$install_mode" != "venv" ]]; then
        log "WARN" "You are in a virtual environment. Consider using --venv flag."
    fi
    
    # Check system dependencies first
    if ! check_system_deps; then
        error_exit "Please install missing system dependencies first"
    fi
    
    # Verify pkexec is available and working
    log "STEP" "Verifying pkexec availability..."
    if ! command_exists "pkexec"; then
        error_exit "pkexec not found. Please install polkit package."
    fi
    
    if ! pkexec --version >/dev/null 2>&1; then
        error_exit "pkexec is not working properly. Please check polkit installation."
    fi
    log "SUCCESS" "pkexec is available and working"
    
    # Find Python executable
    local python_cmd
    if ! python_cmd=$(find_python); then
        error_exit "Compatible Python interpreter not found"
    fi
    
    # If check-only mode, verify current installation and exit
    if [[ "$check_only" == true ]]; then
        log "STEP" "Checking current installation..."
        if verify_installation "$python_cmd"; then
            log "SUCCESS" "ASUC dependencies are properly installed"
            exit 0
        else
            log "ERROR" "Some dependencies are missing or not working"
            exit 1
        fi
    fi
    
    # Handle different installation modes
    case "$install_mode" in
        "venv")
            local venv_path
            venv_path=$(create_venv "$python_cmd")
            python_cmd="$venv_path/bin/python"
            install_python_deps "$python_cmd" "venv"
            ;;
        "user"|"system")
            install_python_deps "$python_cmd" "$install_mode"
            ;;
    esac
    
    # Setup executable scripts
    setup_executables "$python_cmd"
    
    # Verify installation
    if ! verify_installation "$python_cmd"; then
        error_exit "Installation verification failed"
    fi
    
    log "SUCCESS" "ASUC installation completed successfully!"
    log "INFO" "You can now run:"
    
    if [[ "$install_mode" == "venv" ]]; then
        log "INFO" "  GUI: $SCRIPT_DIR/asuc-gui-venv"
        log "INFO" "  CLI: $SCRIPT_DIR/asuc-cli-venv"
        log "INFO" ""
        log "INFO" "Or activate the virtual environment:"
        log "INFO" "  source $SCRIPT_DIR/$VENV_NAME/bin/activate"
        log "INFO" "  $SCRIPT_DIR/asuc-gui"
        log "INFO" "  $SCRIPT_DIR/asuc-cli"
    else
        log "INFO" "  GUI: $SCRIPT_DIR/asuc-gui"
        log "INFO" "  CLI: $SCRIPT_DIR/asuc-cli"
    fi
}

# Run main function with all arguments
main "$@" 