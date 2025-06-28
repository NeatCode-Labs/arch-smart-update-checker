#!/bin/bash

echo "Arch Smart Update Checker - Setup Script"
echo "======================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on Arch-based system
if ! command -v pacman &> /dev/null; then
    echo -e "${RED}Error: This script is designed for Arch Linux systems with pacman.${NC}"
    exit 1
fi

# Recommend pacman-contrib (provides safer 'checkupdates')
if ! command -v checkupdates &> /dev/null; then
    echo -e "${YELLOW}Optional package 'pacman-contrib' is not installed. It provides the safer 'checkupdates' utility used by this tool.${NC}"
    read -p "Install pacman-contrib now? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        install_packages "pacman-contrib"
    else
        echo -e "${YELLOW}Continuing without pacman-contrib. The tool will fall back to a less safe method.${NC}"
    fi
fi

# Function to check if a package is available in pacman repos
check_pacman_package() {
    pacman -Si "$1" &>/dev/null
}

# Function to install packages
install_packages() {
    local packages=("$@")
    echo -e "\n${BLUE}Installing packages: ${packages[*]}${NC}"
    
    if sudo pacman -S --needed --noconfirm "${packages[@]}"; then
        echo -e "${GREEN}✓ Packages installed successfully${NC}"
        return 0
    else
        echo -e "${RED}Failed to install packages${NC}"
        return 1
    fi
}

# Check for Python
echo -e "\n${BLUE}Checking system requirements...${NC}"

if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python is not installed.${NC}"
    read -p "Do you want to install Python? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        install_packages "python"
    else
        echo -e "${RED}Python is required. Exiting.${NC}"
        exit 1
    fi
fi

# Determine Python command
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

echo -e "${GREEN}✓ Python is installed (using $PYTHON_CMD)${NC}"

# Check Python dependencies
echo -e "\n${BLUE}Checking Python dependencies...${NC}"

MISSING_PACKAGES=()
INSTALL_METHOD=""

# Define dependencies and their pacman package names
declare -A DEPENDENCIES=(
    ["feedparser"]="python-feedparser"
    ["colorama"]="python-colorama"
)

# Check each dependency
for module in "${!DEPENDENCIES[@]}"; do
    if ! $PYTHON_CMD -c "import $module" 2>/dev/null; then
        pacman_pkg="${DEPENDENCIES[$module]}"
        
        # Check if available in pacman
        if check_pacman_package "$pacman_pkg"; then
            MISSING_PACKAGES+=("$pacman_pkg")
            echo -e "${YELLOW}✗ $module is not installed (available as $pacman_pkg)${NC}"
        else
            echo -e "${YELLOW}✗ $module is not installed (not available in pacman repos)${NC}"
            INSTALL_METHOD="pip"
        fi
    else
        echo -e "${GREEN}✓ $module is already installed${NC}"
    fi
done

# Handle missing dependencies
if [ ${#MISSING_PACKAGES[@]} -gt 0 ] || [ "$INSTALL_METHOD" = "pip" ]; then
    echo -e "\n${YELLOW}Missing dependencies detected!${NC}"
    
    # If all deps are available in pacman
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ] && [ "$INSTALL_METHOD" != "pip" ]; then
        echo -e "The following packages need to be installed via pacman:"
        printf '%s\n' "${MISSING_PACKAGES[@]}"
        
        read -p "Do you want to install them now? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            install_packages "${MISSING_PACKAGES[@]}"
        else
            echo -e "${RED}Dependencies are required. Please install them manually:${NC}"
            echo "sudo pacman -S ${MISSING_PACKAGES[*]}"
            exit 1
        fi
    else
        # Some packages not in pacman, need alternative method
        echo -e "${YELLOW}Some dependencies are not available in pacman repos.${NC}"
        echo -e "Choose installation method:"
        echo "1) Use pip with --break-system-packages (not recommended)"
        echo "2) Use pipx for isolated environment (recommended)"
        echo "3) Create a virtual environment"
        echo "4) Exit and install manually"
        
        read -p "Your choice [1-4]: " -n 1 -r
        echo
        
        case $REPLY in
            1)
                echo -e "${YELLOW}Installing with pip (--break-system-packages)...${NC}"
                if $PYTHON_CMD -m pip install --user --break-system-packages -r requirements.txt; then
                    echo -e "${GREEN}✓ Dependencies installed${NC}"
                else
                    echo -e "${RED}Failed to install dependencies${NC}"
                    exit 1
                fi
                ;;
            2)
                # Check if pipx is installed
                if ! command -v pipx &> /dev/null; then
                    echo -e "${YELLOW}pipx is not installed.${NC}"
                    read -p "Install pipx? [Y/n] " -n 1 -r
                    echo
                    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                        install_packages "python-pipx"
                    else
                        echo -e "${RED}pipx is required for this option.${NC}"
                        exit 1
                    fi
                fi
                
                echo -e "${BLUE}Creating isolated environment with pipx...${NC}"
                # Create a wrapper script that uses pipx
                cat > arch-smart-update-checker-pipx.py << 'EOF'
#!/usr/bin/env python3
import subprocess
import sys
import os

# Install dependencies in pipx environment if needed
deps = ["feedparser", "colorama"]
for dep in deps:
    try:
        __import__(dep)
    except ImportError:
        print(f"Installing {dep}...")
        subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)

# Run the actual script
script_path = os.path.join(os.path.dirname(__file__), "arch-smart-update-checker.py")
subprocess.run([sys.executable, script_path] + sys.argv[1:])
EOF
                chmod +x arch-smart-update-checker-pipx.py
                echo -e "${YELLOW}Note: Using pipx wrapper. The command will be 'asuc' but will use pipx internally.${NC}"
                SCRIPT_PATH=$(realpath "arch-smart-update-checker-pipx.py")
                ;;
            3)
                echo -e "${BLUE}Creating virtual environment...${NC}"
                if $PYTHON_CMD -m venv venv; then
                    source venv/bin/activate
                    pip install -r requirements.txt
                    deactivate
                    
                    # Create wrapper script
                    cat > arch-smart-update-checker-venv.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/arch-smart-update-checker.py" "$@"
deactivate
EOF
                    chmod +x arch-smart-update-checker-venv.sh
                    SCRIPT_PATH=$(realpath "arch-smart-update-checker-venv.sh")
                    echo -e "${GREEN}✓ Virtual environment created${NC}"
                    echo -e "${YELLOW}Note: Using virtual environment wrapper${NC}"
                else
                    echo -e "${RED}Failed to create virtual environment${NC}"
                    exit 1
                fi
                ;;
            4)
                echo -e "${BLUE}Please install dependencies manually and run setup again.${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid choice${NC}"
                exit 1
                ;;
        esac
    fi
else
    echo -e "\n${GREEN}All Python dependencies are satisfied!${NC}"
fi

# Get the script path
if [ -z "$SCRIPT_PATH" ]; then
    SCRIPT_PATH=$(realpath "arch-smart-update-checker.py")
fi

# Add alias to .bashrc
echo ""
echo "Adding alias to .bashrc..."
ALIAS_LINE="alias asuc='$SCRIPT_PATH'"

# Check if alias already exists
if grep -q "alias asuc=" ~/.bashrc; then
    echo "Alias 'asuc' already exists in .bashrc"
else
    echo "$ALIAS_LINE" >> ~/.bashrc
    echo "Added alias: asuc"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Usage:"
echo "  asuc          - Run the smart update checker"
echo "  asuc -a       - Show all news, not just relevant"
echo "  asuc --non-interactive - Run without prompts (exit status indicates warnings)"
echo "  asuc --help   - Show all options"
echo ""
echo "Please run 'source ~/.bashrc' or restart your terminal to use the alias." 