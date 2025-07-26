#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Arch Smart Update Checker - Uninstall Script
# This script removes all cache and configuration files/folders used by ASUC

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script name for logging
SCRIPT_NAME="ASUC Uninstaller"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[${SCRIPT_NAME}]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[${SCRIPT_NAME}]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[${SCRIPT_NAME}]${NC} $1"
}

print_error() {
    echo -e "${RED}[${SCRIPT_NAME}]${NC} $1"
}

# Function to safely remove a directory or file
safe_remove() {
    local path="$1"
    local description="$2"
    
    if [ -e "$path" ]; then
        if [ -d "$path" ]; then
            if [ "$DRY_RUN" = true ]; then
                print_info "[DRY RUN] Would remove $description directory: $path"
                ((ITEMS_REMOVED++))
            else
                print_info "Removing $description directory: $path"
                if rm -rf "$path" 2>/dev/null; then
                    print_success "Removed $description directory"
                    ((ITEMS_REMOVED++))
                else
                    print_error "Failed to remove $description directory: $path"
                fi
            fi
        elif [ -f "$path" ]; then
            if [ "$DRY_RUN" = true ]; then
                print_info "[DRY RUN] Would remove $description file: $path"
                ((ITEMS_REMOVED++))
            else
                print_info "Removing $description file: $path"
                if rm -f "$path" 2>/dev/null; then
                    print_success "Removed $description file"
                    ((ITEMS_REMOVED++))
                else
                    print_error "Failed to remove $description file: $path"
                fi
            fi
        fi
    else
        print_info "$description not found: $path"
    fi
}

# Function to read JSON value from config file
get_json_value() {
    local file="$1"
    local key="$2"
    if command -v jq >/dev/null 2>&1; then
        jq -r ".$key // empty" "$file" 2>/dev/null || echo ""
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "import json; data=json.load(open('$file')); val=data.get('$key', ''); print(val if val is not None else '')" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# Show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -c, --config FILE    Specify custom config file location"
    echo "  -h, --help          Show this help message"
    echo "  -f, --force         Skip confirmation prompt"
    echo "  -n, --dry-run       Show what would be removed without actually removing"
    echo
    echo "Example:"
    echo "  $0                           # Use default config location"
    echo "  $0 --config ~/my/config.json # Use custom config file"
    echo "  $0 --dry-run                 # Preview what will be removed"
}

# Main uninstall function
main() {
    # Parse command line arguments
    CONFIG_FILE=""
    FORCE_MODE=false
    DRY_RUN=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -f|--force)
                FORCE_MODE=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}Arch Smart Update Checker Uninstaller${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
    
    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE: Nothing will actually be removed"
        echo
    fi
    
    # Default paths
    DEFAULT_CONFIG_DIR="$HOME/.config/arch-smart-update-checker"
    DEFAULT_CACHE_DIR="$HOME/.cache/arch-smart-update-checker"
    DEFAULT_CONFIG_FILE="$DEFAULT_CONFIG_DIR/config.json"
    
    # Use custom config if specified
    if [ -n "$CONFIG_FILE" ]; then
        if [ -f "$CONFIG_FILE" ]; then
            DEFAULT_CONFIG_FILE="$CONFIG_FILE"
            print_info "Using custom config file: $CONFIG_FILE"
        else
            print_error "Specified config file not found: $CONFIG_FILE"
            exit 1
        fi
    fi
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. This will only remove root's ASUC files."
        print_warning "User files in home directories will not be affected."
        echo
    fi
    
    # Look for custom config locations
    CUSTOM_LOG_PATH=""
    ITEMS_REMOVED=0
    
    # Check if config file exists and read custom paths
    if [ -f "$DEFAULT_CONFIG_FILE" ]; then
        print_info "Found configuration file: $DEFAULT_CONFIG_FILE"
        
        # Try to extract custom log path
        CUSTOM_LOG_PATH=$(get_json_value "$DEFAULT_CONFIG_FILE" "log_file")
        if [ -n "$CUSTOM_LOG_PATH" ] && [ "$CUSTOM_LOG_PATH" != "null" ] && [ "$CUSTOM_LOG_PATH" != "" ]; then
            # Expand ~ to home directory
            CUSTOM_LOG_PATH="${CUSTOM_LOG_PATH/#\~/$HOME}"
            print_info "Found custom log path: $CUSTOM_LOG_PATH"
        else
            CUSTOM_LOG_PATH=""
            print_info "No custom log path configured (using default)"
        fi
    else
        if [ -n "$CONFIG_FILE" ]; then
            print_warning "Config file not found: $DEFAULT_CONFIG_FILE"
        fi
    fi
    
    # Confirm before proceeding
    echo
    print_warning "This will remove ALL Arch Smart Update Checker configuration and cache files!"
    echo -e "${YELLOW}The following will be removed:${NC}"
    echo "  - Configuration directory: $DEFAULT_CONFIG_DIR"
    if [ -d "$DEFAULT_CONFIG_DIR/logs" ]; then
        echo "    └── Including logs directory with $(ls -1 "$DEFAULT_CONFIG_DIR/logs" 2>/dev/null | wc -l) log file(s)"
    fi
    echo "  - Cache directory: $DEFAULT_CACHE_DIR"
    if [ -f "$DEFAULT_CACHE_DIR/update_history.json" ]; then
        echo "    └── Including update history data"
    fi
    if [ -n "$CUSTOM_LOG_PATH" ] && [ "$CUSTOM_LOG_PATH" != "" ]; then
        echo "  - Custom log file: $CUSTOM_LOG_PATH"
    fi
    echo
    
    if [ "$FORCE_MODE" = false ]; then
        read -p "Are you sure you want to continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Uninstall cancelled"
            exit 0
        fi
    else
        print_info "Force mode enabled, skipping confirmation"
    fi
    
    echo
    print_info "Starting uninstallation..."
    echo
    
    # Remove default configuration directory
    safe_remove "$DEFAULT_CONFIG_DIR" "configuration"
    
    # Remove default cache directory
    safe_remove "$DEFAULT_CACHE_DIR" "cache"
    
    # Remove default logs directory if verbose logging was enabled
    DEFAULT_LOGS_DIR="$DEFAULT_CONFIG_DIR/logs"
    if [ -d "$DEFAULT_LOGS_DIR" ]; then
        safe_remove "$DEFAULT_LOGS_DIR" "logs"
    fi
    
    # Remove custom log file if it exists and is outside default directories
    if [ -n "$CUSTOM_LOG_PATH" ]; then
        # Only remove if it's not in the default directories (which are already removed)
        if [[ ! "$CUSTOM_LOG_PATH" =~ ^"$DEFAULT_CONFIG_DIR" ]] && [[ ! "$CUSTOM_LOG_PATH" =~ ^"$DEFAULT_CACHE_DIR" ]]; then
            safe_remove "$CUSTOM_LOG_PATH" "custom log"
            
            # Also check for log rotation files (e.g., application.log.1, application.log.2)
            LOG_DIR=$(dirname "$CUSTOM_LOG_PATH")
            LOG_BASE=$(basename "$CUSTOM_LOG_PATH")
            
            for rotated_log in "$LOG_DIR/$LOG_BASE".{1..10} "$LOG_DIR/$LOG_BASE".old "$LOG_DIR/$LOG_BASE".bak; do
                if [ -f "$rotated_log" ]; then
                    safe_remove "$rotated_log" "rotated log"
                fi
            done
            
            # Try to remove the parent directory if it's empty and ASUC-specific
            if [ -d "$LOG_DIR" ] && [[ "$LOG_DIR" =~ arch-smart-update-checker ]]; then
                if [ -z "$(ls -A "$LOG_DIR" 2>/dev/null)" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        print_info "[DRY RUN] Would remove empty log directory: $LOG_DIR"
                    else
                        print_info "Removing empty log directory: $LOG_DIR"
                        rmdir "$LOG_DIR" 2>/dev/null || true
                    fi
                fi
            fi
        fi
    fi
    
    # Check for any window geometry files (sometimes stored separately)
    WINDOW_GEOMETRY_FILE="$HOME/.config/arch-smart-update-checker-geometry.json"
    if [ -f "$WINDOW_GEOMETRY_FILE" ]; then
        safe_remove "$WINDOW_GEOMETRY_FILE" "window geometry"
    fi
    
    # Remove any temporary files that might exist
    TEMP_PATTERNS=(
        "/tmp/asuc-*"
        "/tmp/arch-smart-update-checker-*"
        "/var/tmp/asuc-*"
        "/var/tmp/arch-smart-update-checker-*"
    )
    
    for pattern in "${TEMP_PATTERNS[@]}"; do
        for file in $pattern; do
            if [ -e "$file" ]; then
                safe_remove "$file" "temporary"
            fi
        done
    done
    
    # Remove systemd user service files if they exist
    SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
    if [ -d "$SYSTEMD_USER_DIR" ]; then
        for service in "$SYSTEMD_USER_DIR"/asuc*.service "$SYSTEMD_USER_DIR"/arch-smart-update-checker*.service; do
            if [ -f "$service" ]; then
                service_name=$(basename "$service")
                if [ "$DRY_RUN" = true ]; then
                    print_info "[DRY RUN] Would stop and disable systemd service: $service_name"
                else
                    print_info "Stopping and disabling systemd service: $service_name"
                    systemctl --user stop "$service_name" 2>/dev/null || true
                    systemctl --user disable "$service_name" 2>/dev/null || true
                fi
                safe_remove "$service" "systemd service"
            fi
        done
    fi
    
    # Check for desktop entries
    DESKTOP_DIRS=(
        "$HOME/.local/share/applications"
        "$HOME/.config/autostart"
    )
    
    for dir in "${DESKTOP_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            for desktop_file in "$dir"/asuc*.desktop "$dir"/arch-smart-update-checker*.desktop; do
                if [ -f "$desktop_file" ]; then
                    safe_remove "$desktop_file" "desktop entry"
                fi
            done
        fi
    done
    
    echo
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN COMPLETE!"
        
        # Summary
        if [ $ITEMS_REMOVED -gt 0 ]; then
            print_info "Would remove $ITEMS_REMOVED item(s)"
        else
            print_warning "No items would be removed (nothing was found)"
        fi
    else
        print_success "Uninstallation complete!"
        
        # Summary
        if [ $ITEMS_REMOVED -gt 0 ]; then
            print_success "Successfully removed $ITEMS_REMOVED item(s)"
        else
            print_warning "No items were removed (nothing was found to remove)"
        fi
    fi
    echo
    
    # Final notes
    print_info "Note: The ASUC executables were not removed by this script."
    print_info "To remove the executables, you may need to:"
    echo "  - Remove asuc-cli and asuc-gui from your PATH"
    echo "  - Delete the installation directory if installed from source"
    echo "  - Use your package manager if installed via AUR"
    echo
    
    # Check if executables are in common locations
    FOUND_EXECUTABLES=false
    for exe in asuc-cli asuc-gui; do
        if command -v "$exe" >/dev/null 2>&1; then
            exe_path=$(command -v "$exe")
            print_warning "Found executable: $exe_path"
            FOUND_EXECUTABLES=true
        fi
    done
    
    # If custom config was used, remind user to remove it
    if [ -n "$CONFIG_FILE" ] && [ -f "$CONFIG_FILE" ]; then
        echo
        print_warning "Note: The custom config file was not removed: $CONFIG_FILE"
        print_info "You may want to remove it manually if no longer needed."
    fi
}

# Run main function
main "$@" 