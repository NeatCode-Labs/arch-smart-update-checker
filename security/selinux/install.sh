#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# SELinux policy installation script for Arch Smart Update Checker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Check if SELinux is installed
if ! command -v semodule &> /dev/null; then
    echo -e "${RED}SELinux is not installed. Please install it first:${NC}"
    echo "For Arch Linux, you need to:"
    echo "1. Install SELinux packages from AUR"
    echo "2. Configure your system for SELinux"
    echo "3. Reboot with SELinux enabled"
    exit 1
fi

# Check if SELinux is enabled
if ! selinuxenabled 2>/dev/null; then
    echo -e "${RED}SELinux is not enabled${NC}"
    echo "Please enable SELinux and reboot before installing this policy"
    exit 1
fi

# Check for required SELinux development files
if [ ! -f /usr/share/selinux/devel/Makefile ]; then
    echo -e "${RED}SELinux development files not found${NC}"
    echo "Please install selinux-policy-devel or equivalent package"
    exit 1
fi

# Get SELinux status
SELINUX_MODE=$(getenforce)
echo -e "${GREEN}SELinux is enabled in $SELINUX_MODE mode${NC}"

# Build the policy module
echo -e "${GREEN}Building SELinux policy module...${NC}"
make clean
make

if [ ! -f asuc.pp ]; then
    echo -e "${RED}Failed to build policy module${NC}"
    exit 1
fi

# Install the policy module
echo -e "${GREEN}Installing SELinux policy module...${NC}"
make install

# Check if the module was loaded
if semodule -l | grep -q "^asuc"; then
    echo -e "${GREEN}✓ SELinux policy module successfully installed${NC}"
    
    # Set contexts for existing files
    echo -e "${GREEN}Setting file contexts...${NC}"
    
    # Set contexts for executables if they exist
    for exe in /usr/bin/asuc-cli /usr/bin/asuc-gui; do
        if [ -f "$exe" ]; then
            chcon -t asuc_exec_t "$exe" 2>/dev/null || true
        fi
    done
    
    # Relabel user directories
    echo -e "${GREEN}Relabeling user directories...${NC}"
    for homedir in /home/*; do
        if [ -d "$homedir/.config/asuc" ]; then
            restorecon -R "$homedir/.config/asuc" 2>/dev/null || true
        fi
        if [ -d "$homedir/.cache/asuc" ]; then
            restorecon -R "$homedir/.cache/asuc" 2>/dev/null || true
        fi
    done
    
    echo
    echo -e "${GREEN}SELinux policy installation complete!${NC}"
    echo
    echo "To test the policy in permissive mode for the asuc domain:"
    echo "  semanage permissive -a asuc_t"
    echo
    echo "To enforce the policy:"
    echo "  semanage permissive -d asuc_t"
    echo
    echo "To check for SELinux denials:"
    echo "  ausearch -m avc -ts recent"
    echo "  or"
    echo "  journalctl -t setroubleshoot"
else
    echo -e "${RED}✗ Failed to load SELinux policy module${NC}"
    exit 1
fi 