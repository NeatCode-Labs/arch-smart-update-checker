#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# AppArmor profile installation script for Arch Smart Update Checker

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

# Check if AppArmor is installed
if ! command -v apparmor_parser &> /dev/null; then
    echo -e "${RED}AppArmor is not installed. Please install it first:${NC}"
    echo "sudo pacman -S apparmor"
    exit 1
fi

# Check if AppArmor service is enabled
if ! systemctl is-enabled apparmor &> /dev/null; then
    echo -e "${YELLOW}AppArmor service is not enabled. Enabling it...${NC}"
    systemctl enable apparmor
fi

# Check if AppArmor service is running
if ! systemctl is-active apparmor &> /dev/null; then
    echo -e "${YELLOW}AppArmor service is not running. Starting it...${NC}"
    systemctl start apparmor
fi

# Install the profile
echo -e "${GREEN}Installing AppArmor profile for Arch Smart Update Checker...${NC}"
cp usr.bin.asuc /etc/apparmor.d/

# Load the profile
echo -e "${GREEN}Loading AppArmor profile...${NC}"
apparmor_parser -r /etc/apparmor.d/usr.bin.asuc

# Verify the profile is loaded
if aa-status | grep -q "asuc"; then
    echo -e "${GREEN}✓ AppArmor profile successfully installed and loaded${NC}"
    echo
    echo "The profile is now active in enforce mode."
    echo "To put it in complain mode for testing, run:"
    echo "  sudo aa-complain /usr/bin/asuc-cli"
    echo "  sudo aa-complain /usr/bin/asuc-gui"
    echo
    echo "To re-enable enforce mode, run:"
    echo "  sudo aa-enforce /usr/bin/asuc-cli"
    echo "  sudo aa-enforce /usr/bin/asuc-gui"
else
    echo -e "${RED}✗ Failed to load AppArmor profile${NC}"
    exit 1
fi 